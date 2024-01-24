import argparse
import logging
import tomllib
from datetime import datetime
from pathlib import Path
from fourier_nmr_driver.constants.constants import (
    NMRDefaults,
    NMRSetup,
    RackLayouts,
)
from fourier_nmr_driver.driver.driver import Fourier80
from fourier_nmr_driver.acquisition import SampleBatch, acquire_batch

logging.captureWarnings(True)
logger = logging.getLogger(__name__)

PREFIX = datetime.today().strftime("%Y-%m-%d")

parser = argparse.ArgumentParser(description="Run a batch of NMRs.")
parser.add_argument(
    "--samples",
    default=None,
    help="Batch information file (TOML or JSON).",
)
parser.add_argument(
    "--data",
    default=None,
    help="Path to save the NMR data.",
)
parser.add_argument(
    "--rack",
    action="store",
    choices=["KUKA", "PAL"],
    help="Specify rack type (overwrites the configuration file).",
)
parser.add_argument(
    "--dry",
    action="store_true",
    help="Perform a dry run (no samples will be run).",
)
parser.add_argument(
    "--logfile",
    default=f"{PREFIX}-NMR.log",
    help="Name of the logging file.",
)
parser.add_argument(
    "--settings",
    default=None,
    help="TOML file with acquisition settings.",
)

args = parser.parse_args()

Path(args.logfile).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    filename=args.logfile,
    filemode="a",
    format="%(asctime)s - %(levelname)s (%(name)s) - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)


if args.settings is not None:
    settings_path = (Path.cwd() / args.settings).resolve()
    with open(settings_path, "rb") as f:
        settings = tomllib.load(f)
    NMR_SETUP = NMRSetup(**settings["nmr"])
    NMR_DEFAULTS = NMRDefaults(**settings["defaults"])
    logger.info(f"Settings loaded from {args.settings}.")

else:
    NMR_SETUP = NMRSetup()
    NMR_DEFAULTS = NMRDefaults()
    logger.info("Default settings loaded.")

if args.samples is not None:
    samples_path = (Path.cwd() / args.samples).resolve()

else:
    samples_path = (Path.cwd() / NMR_DEFAULTS.samples_file).resolve()

logger.info(f"Acquiring spectra specified in {samples_path}.")

if args.data is None:
    data_path = (Path.cwd() / f"{PREFIX}-{samples_path.stem}-NMR").resolve()

else:
    data_path = (Path.cwd() / Path(args.data)).resolve()
logger.info(f"Data will be saved in {data_path}.")

if args.rack is not None:
    NMR_SETUP.rack_layout = args.rack

RACKS = RackLayouts.get_racks(layout=NMR_SETUP.rack_layout)
logger.info(f"Using {NMR_SETUP.rack_layout} racks.")

FOURIER = Fourier80()
logger.info(f"Fourier80 REST interface connected at {FOURIER.url}.")


def main():
    """Execute the acquisition code."""
    logger.info(f"Code running in {Path.cwd()}.")

    acquire_batch(
        samples=SampleBatch.from_file(samples_path),
        name=samples_path.stem,
        data_path=data_path,
        dry=args.dry,
    )


if __name__ == "__main__":
    main()
