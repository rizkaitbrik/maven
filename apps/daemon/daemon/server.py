"""gRPC server for Maven daemon."""

from concurrent import futures
from pathlib import Path

import grpc
from core import maven_pb2, maven_pb2_grpc
from maven_logging import get_logger

from daemon.service import MavenDaemon


class DaemonServiceImpl(maven_pb2_grpc.DaemonServiceServicer):
    """Implementation of DaemonService gRPC interface."""
    
    def __init__(self, daemon: MavenDaemon):
        """Initialize the service.
        
        Args:
            daemon: Maven daemon instance
        """
        self.daemon = daemon
        self.logger = get_logger('daemon.grpc')
    
    def Ping(self, request, context):
        """Check if daemon is alive."""
        self.logger.debug("Ping request received")
        return maven_pb2.PingResponse(
            alive=True,
            version="1.0.0"
        )
    
    def GetStatus(self, request, context):
        """Get daemon status."""
        self.logger.debug("GetStatus request received")
        
        status = self.daemon.get_status()
        
        return maven_pb2.StatusResponse(
            running=status.get('running', False),
            indexing=status.get('indexing', False),
            watcher_active=status.get('watcher_active', False),
            files_indexed=status.get('files_indexed', 0),
            uptime=status.get('uptime', ''),
            pid=status.get('pid', 0) or 0
        )
    
    def StartIndexing(self, request, context):
        """Start indexing."""
        self.logger.info("StartIndexing request received", root=request.root_path, rebuild=request.rebuild)
        
        root = Path(request.root_path) if request.root_path else None
        success = self.daemon.start_indexing(root, request.rebuild)
        
        if success:
            return maven_pb2.IndexResponse(
                started=True,
                message="Indexing started"
            )
        else:
            return maven_pb2.IndexResponse(
                started=False,
                message="Indexing already in progress or failed to start"
            )
    
    def StopIndexing(self, request, context):
        """Stop indexing."""
        self.logger.info("StopIndexing request received")
        
        success = self.daemon.stop_indexing()
        
        if success:
            return maven_pb2.StopResponse(
                stopped=True,
                message="Indexing stopped"
            )
        else:
            return maven_pb2.StopResponse(
                stopped=False,
                message="Indexing not in progress"
            )
    
    def GetIndexStats(self, request, context):
        """Get index statistics."""
        self.logger.debug("GetIndexStats request received")
        
        stats = self.daemon.get_index_stats()
        
        return maven_pb2.StatsResponse(
            file_count=stats.get('file_count', 0),
            total_size_bytes=stats.get('total_size_bytes', 0),
            last_indexed_at=stats.get('last_indexed_at', 0.0) or 0.0,
            db_path=stats.get('db_path', '')
        )
    
    def Shutdown(self, request, context):
        """Shutdown the daemon."""
        self.logger.info("Shutdown request received")
        
        # Schedule shutdown
        import threading
        def delayed_shutdown():
            import time
            time.sleep(1)  # Give time to send response
            self.daemon.stop()
        
        threading.Thread(target=delayed_shutdown, daemon=True).start()
        
        return maven_pb2.ShutdownResponse(
            shutdown=True,
            message="Daemon shutting down"
        )


def create_grpc_server(daemon: MavenDaemon, host: str, port: int) -> grpc.Server:
    """Create and configure gRPC server.
    
    Args:
        daemon: Maven daemon instance
        host: Host to bind to
        port: Port to bind to
        
    Returns:
        Configured gRPC server
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Add service
    maven_pb2_grpc.add_DaemonServiceServicer_to_server(
        DaemonServiceImpl(daemon),
        server
    )
    
    # Bind to address
    address = f'{host}:{port}'
    server.add_insecure_port(address)
    
    return server

