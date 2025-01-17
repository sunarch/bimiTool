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

import logging
import unittest

import test_bimibase

logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s [%(levelname)8s] \
                            Module %(name)s in %(funcName)s(%(lineno)s): %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(test_bimibase.TestBimiBase)
    unittest.TextTestRunner(verbosity=2).run(suite)
