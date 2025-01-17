#!/usr/bin/env python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-
# ----------------------------------------------------------------------------#
#    Copyright 2012 Julian Weitz                                              #
#    Copyright 2022 András Németh                                             #
#                                                                             #
#    This program is free software: you can redistribute it and/or modify     #
#    it under the terms of the GNU General Public License as published by     #
#    the Free Software Foundation, either version 3 of the License, or        #
#    any later version.                                                       #
#                                                                             #
#    This program is distributed in the hope that it will be useful,          #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of           #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
#    GNU General Public License for more details.                             #
#                                                                             #
#    You should have received a copy of the GNU General Public License        #
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.    #
# ----------------------------------------------------------------------------#

import copy
import logging
import os
import sys

try:
    import yaml
except ImportError:
    print('----------------------------------------------------------------------')
    print('| Check your python yaml setup! (Debian/Ubuntu: install python-yaml) |')
    print('----------------------------------------------------------------------')
    sys.exit(1)


class BimiConfig:

    _logger = logging.getLogger('BimiConfig')
    _script_dir = os.path.realpath(os.path.dirname(sys.argv[0]))
    _config_file_path = os.path.join(_script_dir, 'bmt_config.yaml')

    # Initialize default configuration
    _default_config_dict = {'db_path': os.path.join(_script_dir, 'bmt_db.sqlite'),
                            'gui_path': os.path.join(_script_dir, 'bmt.glade'),
                            'mail_path': os.path.join(_script_dir, 'mail.txt'),
                            'currency': '€',
                            'deposit': 0.0,
                            'num_comboboxes': 4,
                            'mail_text':
                                '''Guten Tag werter Flur,
die aktuelle Abrechnung der Getränkeliste zeigt folgende Kontostände:

    $accInfos:$name $balance

des Weiteren präsentiere ich für jede Getränkeklasse die Königinnen und Könige:

    $kings:$drink-King ist $name mit $amount Flaschen

Auf ein munteres Weiterzechen!
Euer BiMi'''}

    _config_dict = _default_config_dict

    # Options that will be removed before dumping the config
    _rm_opts = ['db_path', 'gui_path', 'mail_path']

    @staticmethod
    def config():
        """Returns a copy of _config_dict.

        :return: Dictionary copy containing all config options
        """

        return copy.deepcopy(BimiConfig._config_dict)

    @staticmethod
    def load(conf_file_path=None):
        """Loads config options from a file or sets the defaults

        Raises exceptions if no file can be found at conf_file_path or if file
        is not a yaml file.

        :param conf_file_path: String (const) containing the path to the conf file
        :return:
        """

        if conf_file_path is not None:
            BimiConfig._config_file_path = conf_file_path

        try:
            with open(BimiConfig._config_file_path, 'r', encoding='UTF-8') as yaml_file:
                BimiConfig._config_dict = yaml.safe_load(yaml_file)
        except IOError as err:
            if conf_file_path is None:
                BimiConfig._logger.debug('No config file found. Writing one to %s',
                                         BimiConfig._config_file_path)
                BimiConfig.write_config()
            else:
                BimiConfig._logger.error('Reading file %s failed! Using default configuration. \
                                          [io: %s]',
                                         BimiConfig._config_file_path, err)
            return
        except yaml.YAMLError as yamlerr:
            BimiConfig._logger.error('%s is not a valid config file! Using default configuration. \
                                      [yaml: %s]',
                                     BimiConfig._config_file_path, yamlerr)
            return

        if not BimiConfig._config_dict:
            BimiConfig._config_dict = BimiConfig._default_config_dict
            BimiConfig._logger.debug('No options specified in %s. Using default configuration.',
                                     BimiConfig._config_file_path)
            return

        if not isinstance(BimiConfig._config_dict, dict):
            BimiConfig._config_dict = BimiConfig._default_config_dict
            BimiConfig._logger.error('%s is not a valid config file! Using default configuration. \
                                     [yaml: No dictionary found!]',
                                     BimiConfig._config_file_path)
            return

        # Check for mandatory but missing options
        for key, value in BimiConfig._default_config_dict.items():
            if BimiConfig.option(key) is None:
                BimiConfig.set_option(key, value)

    @staticmethod
    def option(option):
        """Returns a copy of the specified option or None if option was not found

        :param option: String (const) key from dictionary _config_dict.
        :return: Object associated to the option string or None if option wasn't found
        """

        try:
            return copy.deepcopy(BimiConfig._config_dict[str(option)])
        except KeyError:
            BimiConfig._logger.debug('Option %s not found!',
                                     option)
            return None

    @staticmethod
    def set_config(conf_dict):
        """Sets the _config_dict to a copy of the given dictionary

        :param conf_dict: Dictionary (const) which will be copied and used as new config
        :return:
        """

        BimiConfig._config_dict = copy.deepcopy(conf_dict)
        BimiConfig.write_config()

    @staticmethod
    def set_option(option, value):
        """Sets or adds a config option in _config_dict

        :param option: String (const) key from dictionary _config_dict
        :param value: Object (const) which will be assoziated with the key
        :return:
        """

        if option not in BimiConfig._config_dict:
            BimiConfig._logger.debug('Adding option %s to _config_dict.',
                                     option)
        BimiConfig._config_dict[option] = copy.deepcopy(value)

    @staticmethod
    def write_config():
        """Writes _config_dict to a yaml file.
        Options specified in _rm_opts are removed before writing.

        TODO: enhance this function.
        """

        # Check if directories exist, if not create them
        if not os.path.isdir(os.path.dirname(BimiConfig._config_file_path)):
            try:
                os.makedirs(os.path.dirname(BimiConfig._config_file_path))
            except OSError as err:
                BimiConfig._logger.error('Not possible to create directory %s! Config not safe O_O \
                                          [os: %s]',
                                         os.path.dirname(BimiConfig._config_file_path), err)

        # Remove specified options before dumping
        dump_dict = copy.deepcopy(BimiConfig._config_dict)
        for item in BimiConfig._rm_opts:
            try:
                del dump_dict[item]
            except KeyError:
                pass

        # Write dictionary to yaml file
        try:
            with open(BimiConfig._config_file_path, 'w', encoding='UTF-8') as yaml_file:
                yaml.safe_dump(dump_dict, stream=yaml_file,
                               default_flow_style=False, allow_unicode=True, encoding='utf-8')
        except IOError as err:
            BimiConfig._logger.error('Oh noes, file %s not writeable! [io: %s]',
                                     BimiConfig._config_file_path, err)
