import asyncio
import uvicorn
import logging
import socketio

from typing import Tuple
from fastapi import FastAPI
from uvicorn import Config, Server

from util import logger
from config import ServerConfig, LoggerConfig

from .routers import get_sio_router, stat_router
from .daq_server import Runner, DAQEvent, EventHandler
from .custom_namespace import CustomNamespace


class DAQHandler(EventHandler):
    def __init__(self, sio):
        self.sio = sio

    async def __call__(self, daq_event: DAQEvent, machine_name: str, machine_msg: Tuple[str, object]):
        namespace = f'{ServerConfig.SIO_PREFIX}/{machine_name}'

        if daq_event == DAQEvent.MESSAGE:
            event, data = machine_msg
            await self.sio.emit(namespace=namespace, event=event, data=data)

        elif daq_event == DAQEvent.CONNECT:
            print(f'{machine_name} connected')
            daq_namespace = CustomNamespace(namespace=namespace)
            self.sio.register_namespace(namespace_handler=daq_namespace)

        elif daq_event == DAQEvent.DISCONNECT:
            del self.sio.namespace_handlers[namespace]
            print(f'{machine_name} disconnected')


class MonitoringApp:
    def __init__(self):
        self.app = FastAPI()
        self.host = ServerConfig.HOST
        self.port = ServerConfig.PORT
        self.sio = socketio.AsyncServer(async_mode='asgi',
                                        cors_allowed_origins=ServerConfig.CORS_ORIGINS)
        self.loop = asyncio.get_event_loop()

        self.daq_server_runner = Runner(host=self.host,
                                        port=ServerConfig.TCP_PORT,
                                        event_handler=DAQHandler(self.sio))
        self._set_logger()
        self._configure_event()
        self._configure_routes()

    def _server_load(self) -> Server:
        uvicorn_log_config = uvicorn.config.LOGGING_CONFIG
        uvicorn_log_config['formatters']['access']['fmt'] = LoggerConfig.FORMAT
        uvicorn_log_config["formatters"]["default"]["fmt"] = LoggerConfig.FORMAT

        socket_app = socketio.ASGIApp(self.sio, self.app)
        config = Config(app=socket_app,
                        host=self.host,
                        port=self.port,
                        loop=self.loop)
        return Server(config)

    def _set_logger(self):
        pass

    def _configure_event(self):
        @self.app.on_event("startup")
        async def startup_event():
            uvicorn_error = logging.getLogger('uvicorn.error')
            uvicorn_access = logging.getLogger('uvicorn.access')

            formatter = logging.Formatter(LoggerConfig.FORMAT)
            uvicorn_error.addHandler(logger.get_file_handler(path=LoggerConfig.PATH,
                                                             name=uvicorn_error.name,
                                                             formatter=formatter))
            uvicorn_access.addHandler(logger.get_file_handler(path=LoggerConfig.PATH,
                                                              name=uvicorn_access.name,
                                                              formatter=formatter))

    def _configure_routes(self):
        sio_router = get_sio_router(self.sio)

        self.app.include_router(sio_router)
        self.app.include_router(stat_router)

    def run(self):
        try:
            self.loop = asyncio.get_event_loop()
            web_server = self._server_load()

            self.daq_server_runner.run()
            self.loop.run_until_complete(web_server.serve())

            self.daq_server_runner.join()
        except Exception as e:
            print(f"An error occurred: {e}")
