#!/usr/bin/env python

"""
Installs packages built from the specs in <component-specs-dir>.
"""


import sys
import os
import glob
import subprocess
import shutil
import argparse

from collections import namedtuple

import json
from planex.globals import RPMS_DIR

CONFIG = "install.json"


ValidationResult = namedtuple('ValidationResult', 'failed, message')
ExecutionResult = namedtuple('ExecutionResult', 'return_code, stdout, stderr')


class SpecsDir(object):
    def __init__(self, root):
        self.root = root

    @property
    def has_config(self):
        return self.root.isfile(self.install_config_path)

    @property
    def install_config_path(self):
        return CONFIG

    @property
    def install_config_is_json(self):
        contents = self.root.getcontents(self.install_config_path)
        try:
            json.loads(contents)
            return True
        except ValueError:
            return False

    def validate(self):
        if self.has_config:
            if not self.install_config_is_json:
                return ValidationResult(
                    failed=True,
                    message='Invalid specs dir: [{0}] is not a json file'.format(
                        self.install_config_path))
        return ValidationResult(
            failed=False,
            message=None)

    def get_package_names_to_install(self):
        pkgs = json.loads(self.root.getcontents(self.install_config_path))
        return [pkg['package-name'] for pkg in pkgs]



class FakeExecutor(object):
    def __init__(self):
        self.results = {}

    def run(self, args):
        assert tuple(args) in self.results, "Unexpected call %s" % args
        return self.results[tuple(args)]


class RPMPackage(object):
    def __init__(self, rpmsdir, path):
        self.path = path
        self.rpmsdir = rpmsdir

    @property
    def name(self):
        result = self.rpmsdir.executor.run(
            ['rpm', '-qp', self.rpmsdir.root.getsyspath(self.path), '--qf', '%{name}'])
        return result.stdout.strip()


class RPMSDir(object):
    def __init__(self, root, executor):
        self.root = root
        self.executor = executor

    @property
    def rpms(self):
        rpms = []
        for rpm_path in self.root.listdir(wildcard='*.rpm'):
            rpms.append(RPMPackage(self, rpm_path))
        return rpms


def parse_config(config_path):
    """Returns list of package names to install. These can be used in
    conjunction with rpm query to find the relevant .rpm files that need
    installing.
    """
    config_file = open(config_path, "r")
    pkgs = json.load(config_file)
    config_file.close()
    return [pkg['package-name'] for pkg in pkgs]


def build_map(rpms_dir):
    """Returns a map from package name to rpm file"""
    result = {}
    for rpm_file in glob.glob(os.path.join(rpms_dir, '*.rpm')):
        pkg_name = subprocess.Popen(
            ["rpm", "-qp", rpm_file, "--qf", "%{name}"],
            stdout=subprocess.PIPE).communicate()[0].strip()
        result[pkg_name] = rpm_file
    return result


def parse_args_or_exit(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('component_dir', help='Specs directory')
    parser.add_argument('dest_dir', help='Destination directory')
    return parser.parse_args(argv)


def main():
    """Main entry point.   Installs packages from <component-dir>
    to <destination-dir>"""

    args = parse_args_or_exit()

    if not os.path.exists(args.component_dir):
        print "Error: directory %s does not exist." % args.component_dir
        sys.exit(1)

    config_path = os.path.join(args.component_dir, CONFIG)
    if not os.path.exists(config_path):
        print ("Config file %s not found, assuming no RPMs need packaging." %
               config_path)
        sys.exit(0)

    if not os.path.exists(args.dest_dir):
        os.makedirs(args.dest_dir)

    config = parse_config(config_path)

    pkg_to_rpm = build_map(RPMS_DIR)

    for pkg_name in config:
        rpm_path = pkg_to_rpm[pkg_name]
        print "Copying:  %s -> %s" % (rpm_path, args.dest_dir)
        shutil.copy(rpm_path, args.dest_dir)


if __name__ == '__main__':
    main()
