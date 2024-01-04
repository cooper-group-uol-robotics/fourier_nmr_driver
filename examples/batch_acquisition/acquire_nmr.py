"""Acquire a batch of NMRs described by a TOML or JSON file."""

import argparse
import json
import logging
import tomllib
from dataclasses import dataclass
from datetime import datetime
from os import PathLike
from pathlib import Path
from time import sleep, time
from typing import Iterable

from fourier_nmr_driver import Fourier80

logger = logging.getLogger()
PREFIX = datetime.today().strftime("%Y-%m-%d")


class RackLayouts:
    """Constants namespace for rack layouts."""

    __slots__ = ()
    KUKARACK1 = [
        *range(40, 46),
        *range(48, 54),
        *range(56, 62),
    ]

    KUKARACK2 = [
        *range(16, 22),
        *range(24, 30),
        *range(32, 38),
    ]

    PALRACK1 = [*range(15, 39)]
    PALRACK2 = [*range(39, 63)]

    @classmethod
    def get_racks(cls, layout: str) -> [int]:
        """Get rack layout.

        Returns actual PAL gripper positions for each rack position.

        Parameters
        ----------
        layout
            Currently implemented "KUKA" and "PAL" racks.

        Returns
        -------
            List of lists with the corresponding sample positions.

        Raises
        ------
        ValueError
            Incorrect rackk configuration.

        """
        match layout.upper():
            case "KUKA":
                return RackLayouts.KUKARACK1, RackLayouts.KUKARACK2
            case "PAL":
                return RackLayouts.PALRACK1, RackLayouts.PALRACK2
            case _:
                raise ValueError("Invalid rack configuration.")


@dataclass
class AcquisitionParameters:
    """A class containing acquisition parameters."""

    parameters: str
    num_scans: int


@dataclass
class NMRSample:
    """A class containing sample information."""

    position: int
    solvent: str
    sample_info: str | dict
    experiments: Iterable[AcquisitionParameters]


class SampleBatch:
    """A class containing a batch of samples."""

    def __init__(self, samples: Iterable[NMRSample]):
        """Initialise SampleBatch.

        Parameters
        ----------
        samples
            A list of NMR samples.

        """
        self.samples = samples

    def __getitem__(self, index):
        return self.samples[index]

    @classmethod
    def from_file(
        cls,
        samples_path: PathLike,
    ):
        """Initialise SampleBatch from a TOML or JSON file.

        Parameters
        ----------
        samples_path
            Path to the file containing batch information.

        """
        samples_path = Path(samples_path)
        match samples_path.suffix:
            case ".toml":
                with open(samples_path, "rb") as f:
                    samples = tomllib.load(f)
                    logger.info(f"Loaded {len(samples)} sample request(s).")

            case ".json":
                with open(samples_path, "r") as f:
                    samples = json.load(f)
                    logger.info(f"Loaded {len(samples)} sample request(s).")

            case _:
                logger.critical("Only TOML or JSON files are supported.")
                raise NotImplementedError(
                    "Only TOML or JSON files are supported."
                )

        return cls.from_dict(samples)

    @classmethod
    def from_dict(
        cls,
        samples_dict: dict,
    ):
        """Generate SampleBatch from a dictionary.

        Parameters
        ----------
        samples_dict
            A dictionary containing batch information.

        """
        samples = []
        for position, info in samples_dict.items():
            experiments = []
            for exp in info["nmr_experiments"]:
                if type(exp) is str:
                    experiment = AcquisitionParameters(
                        parameters=exp,
                        num_scans=defaults["num_scans"],
                    )

                    if exp == "MULTISUPPDC_f":
                        experiment.pp_threshold = defaults["pp_threshold"]
                        experiment.field_presat = defaults["field_presat"]

                    elif exp == "K_WETDC":
                        experiment.l30 = defaults["l30"]

                elif type(exp) is dict:
                    try:
                        experiment = AcquisitionParameters(
                            parameters=exp["parameters"],
                            num_scans=defaults["num_scans"],
                        )

                    except KeyError:
                        logging.error(
                            f"Unknown parameter set for sample {position} "
                            f"- using {defaults['parameters']}."
                        )
                        experiment = AcquisitionParameters(
                            parameters=defaults["parameters"],
                            num_scans=defaults["num_scans"],
                        )

                    if "num_scans" in exp:
                        experiment.num_scans = exp["num_scans"]

                    if exp["parameters"] == "MULTISUPPDC_f":
                        if "pp_threshold" in exp:
                            experiment.pp_threshold = exp["pp_threshold"]
                        else:
                            experiment.pp_threshold = defaults["pp_threshold"]

                        if "field_presat" in exp:
                            experiment.field_presat = exp["field_presat"]
                        else:
                            experiment.field_presat = defaults["field_presat"]

                    elif exp["parameters"] == "K_WETDC":
                        if "l30" in exp:
                            experiment.l30 = exp["l30"]
                        else:
                            experiment.l30 = defaults["l30"]

                experiments.append(experiment)

            sample = NMRSample(
                position=int(position),
                solvent=info["solvent"]
                if "solvent" in info
                else defaults["solvent"],
                sample_info=info["sample_info"]
                if "sample_info" in info
                else defaults["sample_info"],
                experiments=experiments,
            )

            samples.append(sample)

        return cls(samples)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
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
        default=f"{PREFIX}-Fourier80.log",
        help="Name of the logging file.",
    )
    parser.add_argument(
        "--settings",
        default="settings.toml",
        help="TOML file with acquisition settings.",
    )

    return parser.parse_args()


def parse_settings(settings_file: PathLike) -> (dict, dict):
    """Parse system setup and defaults from the TOML file."""
    with open(settings_file, "rb") as f:
        settings = tomllib.load(f)

    return settings["nmr"], settings["defaults"]


def reshim(shim_sample: int, shim_time: int) -> None:
    """Reshim the magnet.

    Parameters
    ----------
    shim_sample
        Position of the shim sample in the rack.
    shim_time
        Shimming time.

    """
    FOURIER.change_sample(shim_sample)
    logger.info("Shim sample inserted.")
    sleep(nmr["wait_time"])
    FOURIER.start_shimming()
    logger.info("Shimming procedure started.")
    sleep(shim_time)
    FOURIER.stop_shimming()
    logger.info("Quick shim procedure stopped. Resuming acquisition.")


def acquire_batch(
    samples: SampleBatch,
    dry: bool = False,
) -> None:
    """Acquire a batch of NMR spectra.

    Parameters
    ----------
    samples
        SampleBatch containing experiment requirements.
    dry, optional
        If True, no actual spectrometer command will be sent.

    """
    for sample in samples:
        # Re-shim if needed
        if not dry:
            if time.time() - FOURIER.last_shim > nmr["reshim_time"]:
                logger.info("Too much time since last shim - reshimming.")
                reshim(shim_sample=1, shim_time=nmr["shim_time"])

        if 1 <= sample.position <= len(racks[0]):
            pal_position = racks[0][sample.position - 1]
            logger.debug(
                f"Sample will be inserted from PAL position {sample.position}."
            )

        elif (
            len(racks[0]) + 1
            <= sample.position
            <= len(racks[0]) + len(racks[1])
        ):
            pal_position = racks[1][sample.position - len(racks[0]) - 1]
            logger.debug(
                f"Sample will be inserted from PAL position {sample.position}."
            )

        else:
            raise ValueError("No such rack position exists.")
        if not dry:
            FOURIER.change_sample(pal_position)

        logger.info(
            f"Sample {batch_name}-{sample.position:02d} inserted from "
            f"rack position {sample.position:02d}."
        )

        if not dry:
            sleep(nmr["wait_time"])

        name = f"{batch_name}-{sample.position:02d}"
        for n, experiment in enumerate(sample.experiments):
            title = "\n".join(
                [
                    f"{name}",
                    f"{sample.sample_info}",
                    experiment.parameters,
                ]
            )

            if not dry:
                exp = FOURIER.new_experiment(
                    path=data_path,
                    exp_name=name,
                    exp_num=10 * (n + 1),
                    title=title,
                    solvent=sample.solvent,
                    parameters=experiment.parameters,
                    getprosol=True,
                    overwrite=True,
                )
                FOURIER.lock(exp)
                logger.info("Locking Fourier80 has finished.")
                exp.number_scans = experiment.num_scans

            logger.info(
                f"Number of scans for experiment {experiment.parameters} "
                f"(expno {10 * (n + 1)}) on sample "
                f"{name} is {experiment.num_scans}."
            )

            if experiment.parameters == "K_WETDC":
                if not dry:
                    exp.nmr_data.launch(f"L30 {experiment.l30}")
                logger.info(f"K_WETDC: L30 set to {experiment.l30}.")

            if experiment.parameters == "MULTISUPPDC_f":
                logger.info(
                    "MULTISUPPDC_f: presaturation of "
                    f"{experiment.field_presat} and peak picking threshold "
                    f"{experiment.pp_threshold}."
                )
                if not dry:
                    exp.nmr_data.launch(
                        "multisupp13c --c13_decouple bb "
                        f"--fieldpresat {experiment.field_presat} "
                        f"--threshold_pp {experiment.pp_threshold}"
                    )
            else:
                if not dry:
                    exp.nmr_data.launch("xaua")
            logger.info(f"Experiment {experiment.parameters} completed.")

        logger.info(f"Experiments on sample {name} completed.")
    logger.info(f"All spectra acquired for batch '{batch_name}'.")


if __name__ == "__main__":
    args = parse_args()
    nmr, defaults = parse_settings(args.settings)

    logging.basicConfig(
        level=logging.INFO,
        filename=args.logfile,
        filemode="a",
        format="%(asctime)s - %(levelname)s (%(name)s) - %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
    )

    logger.info(f"Code running in {Path.cwd()}.")
    try:
        FOURIER = Fourier80()
        logger.info(f"Fourier80 REST interface connected at {FOURIER.url}.")

    except ConnectionError as e:
        logger.critical(e)

    if args.samples is not None:
        samples_path = Path.cwd() / args.samples

    else:
        samples_path = Path.cwd() / defaults["samples_file"]

    if args.data is None:
        data_path = Path.cwd() / f"{PREFIX}-{samples_path.stem}-NMR"

    else:
        data_path = Path(args.data)

    logger.info(f"Settings loaded from {args.settings}.")
    logger.info(f"Acquiring spectra specified in {samples_path}.")
    logger.info(f"Data will be saved in {data_path}.")

    try:
        if args.rack is not None:
            racks = RackLayouts.get_racks(layout=args.rack)
            logger.info(f"Using {args.rack} rack configuration.")
        else:
            racks = RackLayouts.get_racks(layout=nmr["rack_layout"])
            logger.info(f"Using {nmr['rack_layout']} rack configuration.")
    except ValueError:
        logger.error(
            "Invalid rack configuration, using default PAL racks instead."
        )
        racks = RackLayouts.get_racks(layout="PAL")

    logger.info(
        f"Shim sample in reference rack position {nmr['shim_sample']}."
    )
    logger.info(f"Shimming every {nmr['reshim_time'] / 3600:.2f} hours.")
    logger.info(f"Shimming time will be {nmr['shim_time'] / 60:.2f} minutes.")

    logger.debug("Loading te samples file.")

    if not args.dry:
        FOURIER.stop_shimming()
        logger.info("Quickshim procedure completed.")

    samples = SampleBatch.from_file(samples_path)
    batch_name = samples_path.stem
    acquire_batch(samples, dry=args.dry)

    if not args.dry:
        FOURIER.change_sample(nmr["shim_sample"])
        logger.info(f"Shim sample inserted (position {nmr['shim_sample']}).")
        FOURIER.start_shimming()
        logger.info("Started the quickshim procedure.")
