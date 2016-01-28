import os
import subprocess
import json
import itertools

import logging
from logging import handlers

import click


def is_executable_available(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath = os.path.dirname(program)
    if fpath:
        if is_exe(program):
            return True
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return True

    return False


def get_logger(name, level=None, log_file_path=None):
    if level is None:
        level = LEVELS[os.environ.get('LOG_LEVEL', logging.INFO)]
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler) for handler in logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(
            logging.Formatter(name.upper() + ': %(levelname)s: %(asctime)s %(message)s')
        )
        logger.addHandler(stream_handler)

    if log_file_path:
        has_file_handler = any(
            isinstance(handler, handlers.RotatingFileHandler) for handler in logger.handlers
        )
        if not has_file_handler:
            file_handler = handlers.RotatingFileHandler(log_file_path, maxBytes=10000000)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s %(message)s'))
            logger.addHandler(file_handler)

    return logger


_logger = None
_ipfs_executable = None


LEVEL_CHOICES = (
    logging.DEBUG,
    logging.INFO,
    logging.WARNING,
    logging.ERROR,
    logging.CRITICAL,
    logging.FATAL,
)


def ipfs(*args, **kwargs):
    ipfs_executable = kwargs.get('ipfs_executable', _ipfs_executable)
    logger = kwargs.get('logger', _logger)

    command = tuple(itertools.chain(
        [ipfs_executable],
        args,
    ))
    logger.debug(" ".join(command))
    return subprocess.check_output(command)


def get_pinned_ipfs_objects():
    lines = ipfs("pin", "ls").strip().splitlines()
    return tuple((
        line.partition(' ')[0] for line in lines
    ))


def connect_to_peer(peer_id):
    dht_peer_info = ipfs("dht", "findpeer", peer_id).strip().splitlines()

    for address in dht_peer_info[1:]:
        if "127.0.0.1" in address:
            continue
        elif "/ip4/10.0" in address:
            continue
        elif "ip4" not in address:
            continue

        peer_address = "{addr}/ipfs/{peer_id}".format(
            addr=address.strip(),
            peer_id=peer_id,
        )

        try:
            ipfs("swarm", "connect", peer_address)
        except subprocess.CalledProcessError:
            logger.warning("Error connecting to `%s`", peer_address)
            continue
        else:
            break
    else:
        logger.warning("Unable to establish connection to peer `%s`", peer_id)


def get_ipfs_directory_content(ipfs_address):
    raw_contents = ipfs("ls", ipfs_address).strip().splitlines()
    contents = tuple((
        (v[0], v[2]) for v in (line.strip().split() for line in raw_contents)
    ))
    return contents


def get_peer_manifests(peer_id):
    ipfs_address = ipfs("name", "resolve", peer_id).strip()

    contents = get_ipfs_directory_content(ipfs_address)
    return contents


def get_ipfs_file_contents(ipfs_address):
    file_content = ipfs("cat", ipfs_address).strip()
    return file_content


@click.command()
@click.option(
    '-l', '--level',
    type=click.Choice(LEVEL_CHOICES),
    default=logging.INFO,
)
@click.option(
    '-f', '--log-file',
    type=click.Path(exists=True, dir_okay=False, writable=True),
)
@click.option(
    '-e', '--ipfs-executable',
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    '-c', '--config',
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default="config.json",
)
def main(level, log_file, ipfs_executable, config):
    global _logger
    logger = _logger = get_logger(__file__, level=level, log_file_path=log_file)

    if ipfs_executable is None:
        if is_executable_available('ipfs'):
            ipfs_executable = subprocess.check_output(("which", "ipfs")).strip()
        else:
            msg = (
                "No IPFS executable found.  Please specify one with "
                "--ipfs-executable"
            )
            logger.error(msg)
            raise ValueError(msg)

    global _ipfs_executable
    _ipfs_executable = ipfs_executable

    logger.info("Using IPFS Executable: `%s`", ipfs_executable)
    logger.info("Using Config File: `%s`", os.path.abspath(config))

    with open(config) as config_file:
        config_data = json.load(config_file)

    try:
        peers = config_data["peers"]
    except KeyError:
        logger.error("No `peers` key found in config json")
        raise click.ClickException("Config file contains no peers")

    # establish connection to other consortium peers
    logger.info("Connecting to %s peers", len(peers))
    for peer_id in peers:
        connect_to_peer(peer_id)

    peer_object_manifest = set()

    # resolve manifest addresses
    for peer_id in peers:
        try:
            contents = get_peer_manifests(peer_id)
        except subprocess.CalledProcessError:
            logger.error("Error resolving IPNS entry for peer: %s", peer_id)
            continue

        for ipfs_address, filename in contents:
            if not filename.endswith('.json'):
                logger.info("Skipping non JSON file `%s`: %s", filename, ipfs_address)
                continue
            manifest_raw = get_ipfs_file_contents(ipfs_address)
            manifest = json.loads(manifest_raw)

            if not isinstance(manifest, list):
                logger.error("Manifest `%s:%s` is maliformed.  Must be a JSON list.", filename, ipfs_address)
                continue

            peer_object_manifest.update(manifest)

    existing_pinned_objects = set(get_pinned_ipfs_objects())

    already_pinned_objects = existing_pinned_objects.intersection(peer_object_manifest)
    objects_to_pin = peer_object_manifest - existing_pinned_objects

    logger.info("Found %s total objects in peer manifests", len(peer_object_manifest))
    logger.info("%s peer objects already pinned", len(already_pinned_objects))


    for ipfs_address in objects_to_pin:
        logger.info("Pinning %s", ipfs_address)
        ipfs("pin", "add", ipfs_address)


if __name__ == '__main__':
    main()
