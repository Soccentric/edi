# -*- coding: utf-8 -*-
# Copyright (C) 2016 Matthias Luescher
#
# Authors:
#  Matthias Luescher
#
# This file is part of edi.
#
# edi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# edi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with edi.  If not, see <http://www.gnu.org/licenses/>.

from edi.lib.commandfactory import CommandFactory
from edi.lib.configurationparser import ConfigurationParser
import argparse
import os
from edi.lib.helpers import print_error_and_exit
from edi.lib.shellhelpers import run
from edi.lib.commandfactory import get_sub_commands, get_command


def compose_command_name(current_class):
    if EdiCommand is current_class:
        return EdiCommand.__name__.lower()
    else:
        assert len(current_class.__bases__) == 1
        return "{}.{}".format(compose_command_name(current_class.__bases__[0]),
                              current_class.__name__.lower())


class EdiCommand(metaclass=CommandFactory):

    def clean(self, config_file):
        pass

    def _get_sibling_commands(self):
        assert len(type(self).__bases__) == 1
        commands = []
        parent_command = type(self).__bases__[0]._get_command_name()
        for _, command in get_sub_commands(parent_command).items():
            if command != self.__class__:
                commands.append(command)
        return commands

    def _clean_siblings_and_sub_commands(self, config_file):
        for command in self._get_sibling_commands():
            print("cleaning {}".format(command))
            command().clean(config_file)
            command().clean_sub_commands(config_file)

    def clean_sub_commands(self, config_file):
        command = self._get_sub_command("clean")
        if command:
            command().clean(config_file)

    def _setup_parser(self, config_file, running_in_chroot=False):
        self.config = ConfigurationParser(config_file, running_in_chroot)

    @classmethod
    def _get_command_name(cls):
        return compose_command_name(cls)

    @classmethod
    def _get_short_command_name(cls):
        return cls.__name__.lower()

    @classmethod
    def _get_cli_command_string(cls):
        return cls._get_command_name().replace(".", " ")

    @classmethod
    def _get_command_file_name_prefix(cls):
        return cls._get_command_name().replace(".", "_")

    @classmethod
    def _add_sub_commands(cls, parser):
        title = "{} commands".format(cls._get_short_command_name())
        subparsers = parser.add_subparsers(title=title,
                                           dest="sub_command_name")

        for _, command in get_sub_commands(cls._get_command_name()).items():
            command.advertise(subparsers)

    def _run_sub_command_cli(self, cli_args):
        self._get_sub_command(cli_args.sub_command_name)().run_cli(cli_args)

    def _get_sub_command(self, command):
        sub_command = "{}.{}".format(self._get_command_name(),
                                     command)
        return get_command(sub_command)

    @staticmethod
    def _require_config_file(parser):
        parser.add_argument('config_file',
                            type=argparse.FileType('r', encoding='UTF-8'))

    def _require_sudo(self):
        if os.getuid() != 0:
            print_error_and_exit(("The subcommand '{0}' requires superuser "
                                  "privileges.\n"
                                  "Use 'sudo edi {1} ...'."
                                  ).format(self._get_short_command_name(),
                                           self._get_cli_command_string()))

    def _pack_image(self, tempdir, datadir, name="result"):
        # advanced options such as numeric-owner are not supported by
        # python tarfile library - therefore we use the tar command line tool
        tempresult = "{0}.tar.{1}".format(name,
                                          self.config.get_compression())
        archive_path = os.path.join(tempdir, tempresult)

        cmd = []
        cmd.append("tar")
        cmd.append("--numeric-owner")
        cmd.extend(["-C", datadir])
        cmd.extend(["-acf", archive_path])
        cmd.extend(os.listdir(datadir))
        run(cmd, sudo=True)
        return archive_path

    def _unpack_image(self, image, tempdir, subfolder="rootfs"):
        target_folder = os.path.join(tempdir, subfolder)
        os.makedirs(target_folder, exist_ok=True)

        cmd = []
        cmd.append("tar")
        cmd.append("--numeric-owner")
        cmd.extend(["-C", target_folder])
        cmd.extend(["-axf", image])
        run(cmd, sudo=True)
        return target_folder
