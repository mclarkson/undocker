#!/usr/bin/python

import argparse
import json
import logging
import os
import sys
import tarfile
import tempfile

from contextlib import closing


LOG = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument('--ignore-errors', '-i',
                   action='store_true',
                   help='Ignore OS errors when extracting files')
    p.add_argument('--output', '-o',
                   default='.',
                   help='Output directory (defaults to ".")')
    p.add_argument('--verbose', '-v',
                   action='store_const',
                   const=logging.INFO,
                   dest='loglevel')
    p.add_argument('--debug', '-d',
                   action='store_const',
                   const=logging.DEBUG,
                   dest='loglevel')
    p.add_argument('--list', '--ls',
                   action='store_true',
                   help='List layers in an image')
    p.add_argument('--layer', '-l',
                   action='append',
                   help='Extract only the specified layer')
    p.add_argument('image')

    p.set_defaults(level=logging.WARN)
    return p.parse_args()


def find_layers(img, id):
    with closing(img.extractfile('%s/json' % id)) as fd:
        info = json.load(fd)

    LOG.debug('layer = %s', id)
    for k in ['os', 'architecture', 'author']:
        if k in info:
            LOG.debug('%s = %s', k, info[k])

    yield id
    if 'parent' in info:
        pid = info['parent']
        for layer in find_layers(img, pid):
            yield layer


def main():
    args = parse_args()
    logging.basicConfig(level=args.loglevel)

    try:
        name, tag = args.image.split(':', 1)
    except ValueError:
        name, tag = args.image, 'latest'

    with tempfile.NamedTemporaryFile() as fd:
        fd.write(sys.stdin.read())
        fd.seek(0)
        with tarfile.TarFile(fileobj=fd) as img:
            repos = img.extractfile('repositories')
            repos = json.load(repos)

            try:
                top = repos[name][tag]
            except KeyError:
                LOG.error('failed to find image %s with tag %s',
                          name,
                          tag)
                sys.exit(1)

            LOG.info('extracting image %s (%s)', name, top)
            layers = list(find_layers(img, top))

            if args.list:
                print '\n'.join(reversed(layers))
                sys.exit(0)

            if not os.path.isdir(args.output):
                os.mkdir(args.output)

            for id in reversed(layers):
                if args.layer and not id in args.layer:
                    continue

                LOG.info('extracting layer %s', id)
                with tarfile.TarFile(
                        fileobj=img.extractfile('%s/layer.tar' % id)) as layer:
                    try:
                        layer.extractall(path=args.output)
                    except OSError as exc:
                        if args.ignore_errors:
                            LOG.info('ignoring error: %s',
                                     exc)
                            continue

                        raise


if __name__ == '__main__':
    main()
