import logging
import sys
import traceback
from argparse import ArgumentParser, Namespace
from typing import Dict, List, Optional
from pathlib import Path

import divelog_convert
from divelog_convert.converter import DiveLogConverter

log = logging.getLogger(__name__)


def _parse_args(converter: DiveLogConverter) -> Namespace:
    parser = ArgumentParser(description="Dive logs format conversion")
    parser.add_argument("--input", "-i", help="Input dive log file", required=True)
    parser.add_argument("--output", "-o", help="Output dive log file", required=True)
    parser.add_argument(
        "--input-format", "-if",
        help=f"Optional input format, or detected from file extension. Accepted formats: {converter.decoders}",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--output-format",
        "-of",
        help=f"Optional output format, or detected from file extension. Accepted formats: {converter.encoders}",
        required=False,
        default=None,
    )
    parser.add_argument("--debug", "-d", default=False, action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    args.log_level = logging.DEBUG if args.debug else logging.INFO
    return args


def _setup_logging(level: int = logging.INFO, filename: Optional[str] = None) -> None:
    """Configure standard logging."""
    logging.basicConfig(
        format="%(asctime)s %(filename)s:%(lineno)s %(levelname)s: %(message)s", level=level, filename=filename
    )


def main() -> None:
    """Main entry point."""
    print(f"divelog_convert version {divelog_convert.__version__}", file=sys.stderr)

    converter = DiveLogConverter()
    args = _parse_args(converter)
    _setup_logging(level=args.log_level)

    try:
        converter.convert(args.input, args.output, input_format=args.input_format, output_format=args.output_format)
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.debug:
            traceback.print_exc()
            log.exception(e)
        sys.exit(2)
