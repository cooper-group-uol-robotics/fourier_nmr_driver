# Driver for Bruker Fourier80 NMR in A.I.C. Group

[![DOI](https://zenodo.org/badge/739312998.svg)](https://zenodo.org/doi/10.5281/zenodo.11174257)

## Requirements and installation

Requires the official Bruker TopSpin Python API to be installed in the system.
The API comes shipped with TopSpin from version 4.2.0, which can be obtained
free-of-charge for [academic users](https://www.bruker.com/en/products-and-solutions/mr/nmr-software/topspin.html).

It is probably best to dedicate an isolated conda environment for the package:

```
conda create -n fourier-nmr-driver python>=3.10
conda activate fourier-nmr-driver
```

and use the TopSpin API directly from the wheels provided by Bruker (note that different versions might be supplied with different TopSpin installations), e.g., by copying them into a local `wheels` directory:

```
mkdir wheels
cp <TopSpin-installation-folder>/python/examples/ts_remote_api-2.0.0-py3-none-any.whl wheels/
cp <TopSpin-installation-folder>/python/examples/bruker_nmr_api-1.3.5-py3-none-any.whl wheels/
```

now the package should install correctly:

```
python -m pip install . --find-links wheels
```

## Usage

### TopSpin pre-configuration

The driver requires TopSpin running in the system with the REST inteface started.
To check whether the REST inferface is running correcly, go to:

```Settings > Python 3+ > Manage TopSpin Network Interface```

This setting window requires TopSpin administrator privileges. We recommend
ticking the box "Start every time TopSpin is started".

## Module execution

The package can also be executes as a Python module via:
```
python -m fourier_nmr_driver [SAMPLES.TOML]
```
or directly as a script:
```
nmr [SAMPLES.TOML]
```

### Basic usage

Most operations are performed via an instance of the `Fourier80` class and
associated methods, e.g., `new_experiment()`, `change_sample()` or `start_shimming()`.
Dataset-related operations (such as editing processing or acquisition parameters)
are accessed via an `NMRExperiment` class.

More advanced users of Bruker systems might find it useful to control the TopSpin command-line interface directly, e.g.:

```
FOURIER = Fourier80()
topspin_api = FOURIER.top
topspin_api.executeCommand("efp;apk")
```

## Example

### Batch acquisition

An example script for acquiring spectra can be found in `examples/batch_acquisition`.
It uses a description of a batch of sample in a TOML or JSON file.
The supplied examples should result in equivalent set of experiments.
