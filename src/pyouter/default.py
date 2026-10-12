import argparse


def create_parser(description, tasks="tasks"):
    opt_parser = argparse.ArgumentParser(description=description)

    opt_parser.add_argument(
        'actions',
        metavar='A',
        type=str,
        nargs='?',
        help='actions strings in tree')

    opt_parser.add_argument(
        f'--{tasks}',
        const=True,
        dest='tasks',
        nargs='?',
        help='completion the actions strings'
    )

    opt_parser.add_argument(
        "-s", '--script-name',
        dest="script",
        nargs='?',
        type=str,
        help='completion the actions strings'
    )

    opt_parser.add_argument(
        "-v", "--view",
        dest="view",
        help="view the router track",
        action="store_true",
    )
    
    opt_parser.add_argument(
        "-t", "--tree",
        dest="tree",
        help="print all available router paths or inspect router tree structure",
        action="store_true",
    )

    opt_parser.add_argument(
        "-w", "--web",
        dest="web",
        help="start a local web ui to browse and run routers",
        action="store_true",
    )

    opt_parser.add_argument(
        "--host",
        dest="host",
        default="127.0.0.1",
        help="host for the local web ui (default: 127.0.0.1)",
    )

    opt_parser.add_argument(
        "--port",
        dest="port",
        default=8765,
        type=int,
        help="port for the local web ui (default: 8765)",
    )

    opt_parser.add_argument(
        "--no-browser",
        dest="no_browser",
        help="do not open a browser when starting the web ui",
        action="store_true",
    )

    return opt_parser
