"""Maven daemon main entry point."""

import sys
from pathlib import Path
from retrieval.services.config_manager import ConfigManager
from daemon.service import MavenDaemon
from daemon.server import create_grpc_server
from maven_logging import get_logger


def main():
    """Main entry point for Maven daemon."""
    # Load configuration
    try:
        config_manager = ConfigManager()
        config = config_manager.config
    except Exception as e:
        print(f"Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize logger
    logger = get_logger(
        'daemon.main',
        log_dir=Path(config.logging.log_dir).expanduser(),
        level=config.logging.level
    )

    try:
        # Create daemon
        daemon = MavenDaemon(config)

        # Start daemon
        daemon.start()

        # Create and start gRPC server
        grpc_server = create_grpc_server(
            daemon,
            config.daemon.grpc_host,
            config.daemon.grpc_port
        )
        grpc_server.start()

        logger.info(
            "gRPC server started",
            host=config.daemon.grpc_host,
            port=config.daemon.grpc_port
        )

        # Wait for shutdown
        daemon.wait()

        # Stop gRPC server
        grpc_server.stop(grace=5)
        logger.info("gRPC server stopped")

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        daemon.stop()
    except Exception as e:
        logger.exception("Daemon error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
