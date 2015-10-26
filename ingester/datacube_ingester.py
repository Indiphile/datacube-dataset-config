import click
import os
import pathlib
import logging
from create_tiles import calc_output_filenames, create_tiles, list_tile_files
from ingester.utils import preserve_cwd
from netcdf_writer import append_to_netcdf, MultiVariableNetCDF, SingleVariableNetCDF
import eodatasets.drivers
import eodatasets.type
from eodatasets.serialise import read_yaml_metadata


_LOG = logging.getLogger(__name__)
CLICK_SETTINGS = dict(help_option_names=['-h', '--help'])
DEFAULT_TILE_OPTIONS = {
    'output_format': 'GTiff',
    'create_options': ['COMPRESS=DEFLATE', 'ZLEVEL=1']
}


def get_input_filenames(input_path, eodataset):
    """
    Extracts absolute filenames from a DatasetMetadata object.

    :type input_path: pathlib.Path
    :type eodataset: eodatasets.type.DatasetMetadata
    :return: list of filenames
    """
    assert input_path.is_dir()
    bands = sorted([band for band_num, band in eodataset.image.bands.items()], key=lambda band: band.number)
    input_files = [input_path / band.path for band in bands]

    return input_files


def is_yaml_file(path):
    """
    Checks if this is a path to a yaml file

    :type path: pathlib.Path
    :rtype: boolean
    """
    return path.is_file() and path.suffix == '.yaml'


def load_dataset(input_path):
    """
    Loads a dataset metadata description

    :param input_path:
    :rtype: (pathlib.Path, eodataset.DatasetMetadata)
    """
    input_path = pathlib.Path(input_path)

    if is_yaml_file(input_path):
        eodataset = read_yaml_metadata(input_path)
        input_path = input_path.parent

    elif input_path.is_dir():
        eodriver = eodatasets.drivers.EODSDriver()
        eodataset = eodatasets.type.DatasetMetadata()
        eodriver.fill_metadata(eodataset, input_path)
    else:
        raise Exception("Unknown dataset type at: {}" % input_path)

    return input_path, eodataset


def merge_tiles_to_netcdf(eodataset, filename_format, netcdf_class):
    created_tiles = list_tile_files('test.csv')
    tile_mappings = calc_output_filenames(created_tiles, filename_format, eodataset)
    for geotiff, netcdf in tile_mappings:
        append_to_netcdf(geotiff, netcdf, eodataset, netcdf_class=netcdf_class)

    return [netcdf_path for _, netcdf_path in tile_mappings]


def setup_logging(verbosity):
    """
    Setups up logging, defaults to WARN

    :param verbosity: 1 for INFO, 2 for DEBUG
    :return:
    """
    logging_level = logging.WARN - 10 * verbosity
    logging.basicConfig(level=logging_level, format='%(asctime)s %(levelname)s %(message)s')


@preserve_cwd
def ingest(input_path, output_dir, filename_format, netcdf_class=MultiVariableNetCDF, tile=True, merge=True):
    """
    Runs a series of steps to: stack, split into tiles and re-merge into netcdf an input dataset

    :param input_path: str, pathname to a ga-metadata.yaml file or directory that eo-datasets can process
    :param output_dir: str, pathname
    :param filename_format: string format for output filenames, extracts fields from the input EO-Dataset
    :param netcdf_class: either MultiVariableNetCDF or SingleVariableNetCDF
    :param tile: boolean, whether to run the tiling step
    :param merge: boolean, whether
    :return: list of created tile-files
    """
    os.chdir(output_dir)

    input_path, eodataset = load_dataset(input_path)

    input_files = get_input_filenames(input_path, eodataset)
    basename = eodataset.ga_label

    if tile:
        created_tiles = create_tiles(input_files, basename, DEFAULT_TILE_OPTIONS)
        _LOG.info("Created tiles: {}".format(created_tiles))

    # Import tiles into NetCDF files
    if merge:
        netcdf_paths = merge_tiles_to_netcdf(eodataset, filename_format, netcdf_class)
        _LOG.info("Created/altered storage units: {}".format(netcdf_paths))

    return netcdf_paths


@click.command(help="Example output filename format: combined_{x}_{y}.nc", context_settings=CLICK_SETTINGS)
@click.option('--output-dir', '-o', default='.')
@click.option('--multi-variable', 'netcdf_class', flag_value=MultiVariableNetCDF, default=True)
@click.option('--single-variable', 'netcdf_class', flag_value=SingleVariableNetCDF)
@click.option('--tile/--no-tile', default=True, help="Allow partial processing")
@click.option('--merge/--no-merge', default=True, help="Allow partial processing")
@click.option('--verbose', '-v', count=True, help="Use multiple times for more verbosity")
@click.argument('input_path', type=click.Path(exists=True, readable=True))
@click.argument('filename-format')
def main(input_path, output_dir, filename_format, netcdf_class=MultiVariableNetCDF,
         tile=True, merge=True, verbose=0):
    """
    Runs ingest from the command line
    """
    setup_logging(verbose)

    ingest(input_path, output_dir, filename_format, netcdf_class, tile, merge)


if __name__ == '__main__':
    try:
        from ipdb import launch_ipdb_on_exception
        with launch_ipdb_on_exception():
            main()
    except ImportError:
        main()
