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

import datetime
import os
import sqlite3
import unittest

import bimibase


class TestBimiBase(unittest.TestCase):

    db_path = '/tmp/unit_test_db.sqlite'

    def build_database(self, db_path=None):
        if not db_path:
            db_path = TestBimiBase.db_path

        self.dbcon = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.cur = self.dbcon.cursor()

        self.cur.execute('CREATE TABLE accounts(aid INTEGER PRIMARY KEY,\
                                                name TEXT)')

        self.cur.execute('CREATE TABLE drinks(did INTEGER PRIMARY KEY,\
                                              name TEXT,\
                                              sales_price INTEGER,\
                                              purchase_price INTEGER,\
                                              deposit INTEGER,\
                                              bottles_full INTEGER,\
                                              bottles_empty INTEGER,\
                                              deleted BOOL,\
                                              kings BOOL)')

        self.cur.execute('CREATE TABLE kings(aid INTEGER,\
                                             did INTEGER,\
                                             quaffed INTEGER)')

        self.cur.execute('CREATE TABLE transacts(tid INTEGER,\
                                                 aid INTEGER,\
                                                 did INTEGER,\
                                                 count INTEGER,\
                                                 value INTEGER,\
                                                 date TIMESTAMP)')
        self.dbcon.commit()

    def populate_database(self):
        """ Insert entries into database to enable testing

        accounts
            1 Noob
            2 Max Mustermann
            3 Testa

        drinks
            1 Fanta     100 85 15  5  15 False True
            2 Cola      100 85 15 23   2 False False
            3 Geloescht  20 19 25  0 300 True  False

        kings
            aid did quaffed
              1   1      10
              1   2       2
              3   1       5
              3   3     300

        transacts
            tid aid did count value date
              1   1   0     1  1000   d1
              2   2   0     1   500   d2
              3   3   1     5   100   d3
              3   3   3   300    20   d3
              4   1   1    10   100   d4
              4   1   2     2   100   d4
        """

        self.cur.execute('DELETE FROM accounts')
        self.cur.execute('DELETE FROM drinks')
        self.cur.execute('DELETE FROM kings')
        self.cur.execute('DELETE FROM transacts')

        self.accounts_list = [(1, 'Noob'),
                              (2, 'Max Mustermann'),
                              (3, 'Testa')]
        self.cur.executemany('INSERT INTO accounts VALUES(?,?)', self.accounts_list)

        self.drinks_list = [(1, 'Fanta', 100, 85, 15, 5, 15, False, True),
                            (2, 'Cola', 100, 85, 15, 23, 2, False, False),
                            (3, 'Geloescht', 20, 19, 25, 0, 300, True, False)]
        self.cur.executemany('INSERT INTO drinks VALUES(?,?,?,?,?,?,?,?,?)', self.drinks_list)

        self.kings_list = [(1, 1, 10), (1, 2, 2),
                           (3, 1, 5), (3, 3, 300)]
        self.cur.executemany('INSERT INTO kings VALUES(?,?,?)', self.kings_list)

        self.d1 = datetime.datetime.now()
        self.d2 = datetime.datetime.now()
        self.d3 = datetime.datetime.now()
        self.d4 = datetime.datetime.now()
        self.transacts_list = [(1, 1, 0, 1, 1000, self.d1),
                               (2, 2, 0, 1, 500, self.d2),
                               (3, 3, 1, 5, 100, self.d3),
                               (3, 3, 3, 300, 20, self.d3),
                               (4, 1, 1, 10, 100, self.d4),
                               (4, 1, 2, 2, 100, self.d4)]
        self.cur.executemany('INSERT INTO transacts VALUES(?,?,?,?,?,?)', self.transacts_list)
        self.dbcon.commit()

    def tearDown(self):
        self.bb = None
        self.dbcon = None
        self.cur = None
        os.remove(TestBimiBase.db_path)

    def test_accounts(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        acc_list = list(self.accounts_list)
        acc_list.sort(key=lambda x: x[1])
        self.assertEqual(acc_list, self.bb.accounts())

    def test_add_account_no_credit(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        self.bb.add_account('Neuer')
        self.cur.execute('SELECT * FROM accounts WHERE aid=4')
        self.assertEqual([(4, 'Neuer')], self.cur.fetchall())

    def test_add_credit(self):
        self.build_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        # Empty DB test
        self.bb.add_credit(2, -100)
        self.cur.execute('SELECT tid,aid,did,count,value FROM transacts WHERE tid=1')
        self.assertEqual([(1, 2, 0, 1, -100)], self.cur.fetchall())

        # Populated DB test
        self.populate_database()

        self.bb.add_credit(2, -100)
        self.cur.execute('SELECT tid,aid,did,count,value FROM transacts WHERE tid=5')
        self.assertEqual([(5, 2, 0, 1, -100)], self.cur.fetchall())

    def test_add_drink(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        self.bb.add_drink(['Red Bull', 85, 80, 8, 100, 0, True])
        self.cur.execute('SELECT * FROM drinks WHERE did=4')
        self.assertEqual([(4, 'Red Bull', 85, 80, 8, 100, 0, False, True)], self.cur.fetchall())

    def test_consume_drinks_multiple_dids(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        self.bb.consume_drinks(2, [(1, 10), (2, 20), (2, 30)])

        self.cur.execute('SELECT * FROM drinks WHERE did in (1,2) ORDER BY did ASC')
        self.assertEqual([(1, 'Fanta', 100, 85, 15, 0, 25, False, True),
                         (2, 'Cola', 100, 85, 15, 0, 52, False, False)],
                         self.cur.fetchall())

        self.cur.execute('SELECT * FROM kings WHERE aid=2')
        self.assertEqual([(2, 1, 10), (2, 2, 50)], self.cur.fetchall())

        self.cur.execute('SELECT tid,aid,did,count,value FROM transacts WHERE tid=5')
        self.assertEqual([(5, 2, 1, 10, -100), (5, 2, 2, 50, -100)], self.cur.fetchall())

    def test_del_account(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        self.bb.del_account(1)

        self.cur.execute('SELECT * FROM accounts WHERE aid=1')
        self.assertEqual([], self.cur.fetchall())

        self.cur.execute('SELECT * FROM kings WHERE aid=1')
        self.assertEqual([], self.cur.fetchall())

        self.cur.execute('SELECT * FROM transacts WHERE aid=1')
        self.assertEqual([], self.cur.fetchall())

    def test_del_drink(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        self.bb.del_drink(1)

        self.cur.execute('SELECT * FROM drinks WHERE did=1')
        self.assertEqual([(1, 'Fanta', 100, 85, 15, 5, 15, True, False)], self.cur.fetchall())

    def test_undo_transactions(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        self.transacts_list.pop(0)  # remove transaction with tid=1
        target = {'drinks': self.drinks_list,
                  'kings': self.kings_list,
                  'transacts': self.transacts_list}

        self.bb.undo_transaction(1)

        for item in ['drinks', 'kings', 'transacts']:
            self.cur.execute('SELECT * FROM ' + item)
            self.assertEqual(target[item], self.cur.fetchall())

        self.bb.undo_transaction(3)

        target['drinks'][0] = (1, 'Fanta', 100, 85, 15, 10, 10, False, True)
        target['drinks'][2] = (3, 'Geloescht', 20, 19, 25, 300, 0, True, False)
        target['kings'][2] = (3, 1, 0)
        target['kings'][3] = (3, 3, 0)
        target['transacts'].pop(1)
        target['transacts'].pop(1)
        for item in ['drinks', 'kings', 'transacts']:
            self.cur.execute('SELECT * FROM ' + item)
            self.assertEqual(target[item], self.cur.fetchall())

    def test_drinks(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        # filter drinks with deleted=True and remove bool from tuple list
        buff_list = filter(lambda x: x[7] is False, self.drinks_list)
        check_list = []
        for item in buff_list:
            buff = list(item)
            buff.pop(7)
            check_list.append(tuple(buff))
        check_list.sort(key=lambda x: x[1])

        self.assertEqual(check_list, self.bb.drinks())

    def test_set_drink(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        self.bb.set_drink(2, ['fritz-kola', 101, 86, 16, 24, 3, True])

        self.cur.execute('SELECT * FROM drinks WHERE did=2')
        self.assertEqual([(2, 'fritz-kola', 101, 86, 16, 24, 3, False, True)], self.cur.fetchall())

    def test_kings(self):
        self.build_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        # Empty DB test
        self.assertEqual([], self.bb.kings())

        # Populated DB test
        self.populate_database()

        # Testcase: Same drink name but different dids
        self.bb.add_drink(['MultiDrink', 4, 0, 0, 0, 0, True])
        self.bb.add_drink(['MultiDrink', 5, 0, 0, 0, 0, True])
        self.bb.consume_drinks(2, [(4, 4), (5, 5)])

        expected_result = [('Max Mustermann', 'MultiDrink', 9),
                           ('Noob', 'Fanta', 10)]
        self.assertEqual(expected_result, self.bb.kings())

    def test_transactions(self):
        self.build_database()
        self.populate_database()
        self.bb = bimibase.BimiBase(TestBimiBase.db_path)

        # tid, drinks.name, count, value, date)
        check_list = [(1, None, 1, 1000, self.d1),
                      (4, 'Fanta', 10, 100, self.d4),
                      (4, 'Cola', 2, 100, self.d4)]
        self.assertEqual(check_list, self.bb.transactions(1))
