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

import argparse
import logging
import subprocess
import sys
import urllib.parse

import gi
gi.require_version('Gtk', '3.0')
try:
    from gi.repository import Gtk, Pango
except ImportError:
    print('--------------------------------------------------------------------------')
    print('| Check your python GTK+3 setup! (Debian/Ubuntu: install gir1.2-gtk-3.0) |')
    print('--------------------------------------------------------------------------')
    sys.exit(1)

from bimibase import BimiBase
from bimiconfig import BimiConfig


class BiMiTool:

    def __init__(self):
        self.account_window = None             # The most recent popup window to add/edit accounts
        self.drink_window = None               # The most recent popup window to add/edit drinks
        self.mail_window = None                # The most recent popup window to get the mail text
        self.edit_acc_infos = []               # Stores [account_id, name] while edit_account window is open
        self.edit_drink_infos = []             # Stores row from drinks_list while edit_drink window is open
        self.event_pos = []                    # [x,y] pos from event object that activated the last context menu popup
        self.transactions = []                 # Contains all informations and transactions from one account
        self.drinks_comboxes_spinbuttons = []  # Contains tuples (combobox,spinbutton)
        self.transactions_list = Gtk.ListStore(int, str, str)
        self.accounts_list = Gtk.ListStore(int, str)

        # for each float a str for visualisation
        self.drinks_list = Gtk.ListStore(int,         # did
                                         str,         # dname
                                         float, str,  # sPrice, str sPrice
                                         float, str,  # pPrice, str pPrice
                                         float, str,  # deposit, str deposit
                                         int,         # fBottles
                                         int,         # eBottles
                                         bool,        # kings
                                         str)         # str for comboboxes

        self._logger = logging.getLogger('BiMiTool')

        # Create DataBase-object
        self.db = BimiBase(BimiConfig.option('db_path'))

        # Load main window from GtkBuilder file
        self.gui = Gtk.Builder()
        widgets = ['main_window', 'image1', 'image2', 'image3', 'image1',
                   'drinks_menu', 'accounts_menu', 'transactions_menu',
                   'adjustment7', 'adjustment8', 'adjustment9', 'adjustment10']
        self.gui.add_objects_from_file(BimiConfig.option('gui_path'), widgets)
        try:
            # Create our dictionay and connect it
            dic = {'consume_clicked': self.consume_drinks,
                   'add_account': self.pop_add_acc_window,
                   'edit_account': self.pop_edit_acc_window,
                   'acc_view_button_pressed': self.accounts_view_clicked,
                   'tab_switched': self.tab_switched,

                   'delete_account': self.delete_account,
                   'acc_view_row_act': self.update_transactions_view,
                   'drinks_view_button_pressed': self.drinks_view_clicked,
                   'delete_drink': self.delete_drink,

                   'transactions_view_button_pressed': self.transactions_view_clicked,
                   'undo_transaction': self.undo_transaction,

                   'add_drink': self.pop_add_drink_window,
                   'edit_drink': self.pop_edit_drink_window,

                   'generate_mail': self.show_summary_mail,
                   # 'preferences_activate': self.prefsPopup,
                   'main_window_destroyed': Gtk.main_quit,
                   'quit_activate': Gtk.main_quit}
            self.gui.connect_signals(dic)
        except:
            self._logger.critical('Autoconnection of widgets failed! Check if %s exists.',
                                  BimiConfig.option('gui_path'))
            sys.exit(1)
        self.main_window = self.gui.get_object('main_window')
        self.accounts_context_menu = self.gui.get_object('accounts_menu')
        self.drinks_context_menu = self.gui.get_object('drinks_menu')
        self.transactions_context_menu = self.gui.get_object('transactions_menu')

        # Create column-headers and add accounts from database into rows
        self.accounts_view = self.gui.get_object('accounts_view')
        self.accounts_view.set_model(self.accounts_list)
        self.accounts_name_col = Gtk.TreeViewColumn('Account name', Gtk.CellRendererText(), text=1)
        self.accounts_view.append_column(self.accounts_name_col)
        self.update_accounts_view()

        # Create column headers for drinks_view
        self.drinks_view = self.gui.get_object('drinks_view')
        self.drinks_view.set_model(self.drinks_list)
        col_names = ['Name', 'Sales Price', 'Purchase Price', 'Deposit', 'Full Bottles', 'Empty Bottles', 'Kings']
        render_cols = [1, 3, 5, 7, 8, 9, 10]
        for col_name, render_col in zip(col_names, render_cols):
            renderer = Gtk.CellRendererText()
            renderer.set_alignment(1.0, 0.5)
            drinks_view_col = Gtk.TreeViewColumn(col_name, renderer, text=render_col)
            self.drinks_view.append_column(drinks_view_col)

        # Create column headers for transactions_view
        self.transactions_view = self.gui.get_object('transactions_view')
        self.transactions_view.set_model(self.transactions_list)
        col_names = ['Date', 'Value']
        render_cols = [1, 2]
        for col_name, render_col in zip(col_names, render_cols):
            renderer = Gtk.CellRendererText()
            renderer.set_alignment(1.0, 0.5)
            trans_view_col = Gtk.TreeViewColumn(col_name, renderer, text=render_col)
            self.transactions_view.append_column(trans_view_col)

        # Set up and add text from database to comboboxes and spinbuttons
        grid = self.gui.get_object('drinks_grid')
        num = BimiConfig.option('num_comboboxes')
        for i in range(num):
            cbox = Gtk.ComboBox.new_with_model(self.drinks_list)
            cbox.set_hexpand(True)
            cell = Gtk.CellRendererText()
            cbox.pack_start(cell, True)
            cbox.add_attribute(cell, 'text', 11)

            adjustment = Gtk.Adjustment(value=0, lower=0, upper=999,
                                        step_increment=1, page_increment=10, page_size=0)
            spinbutton = Gtk.SpinButton()
            spinbutton.set_adjustment(adjustment)
            spinbutton.set_numeric(True)
            spinbutton.set_alignment(1.0)
            self.drinks_comboxes_spinbuttons.append((cbox, spinbutton))

            grid.attach(cbox, 0, i, 1, 1)
            grid.attach(spinbutton, 1, i, 1, 1)

        grid.child_set_property(self.gui.get_object('consume_button'), 'top-attach', num+1)
        grid.child_set_property(self.gui.get_object('scrolledwindow1'), 'top-attach', num+2)
        self.update_drinks_list()

        self.main_window.show_all()

    def accounts_view_clicked(self, widget, event):
        """Called if mouse button is pressed in self.accounts_view

        Checks for right mouse click and opens context menu
        """

        if event.button == 3:
            self.event_pos = (event.x, event.y)
            if widget.get_path_at_pos(event.x, event.y) is None:
                self.gui.get_object('acc_menu_edit').set_sensitive(False)
                self.gui.get_object('acc_menu_delete').set_sensitive(False)
            else:
                self.gui.get_object('acc_menu_edit').set_sensitive(True)
                self.gui.get_object('acc_menu_delete').set_sensitive(True)
            self.accounts_context_menu.popup(None, None, None, None, event.button, event.time)
            return True

    def account_window_cancel(self, widget):
        self.account_window.destroy()

    def account_window_destroyed(self, widget):
        self.account_window = None
        self.edit_acc_infos = []

    def account_window_save(self, widget):
        """Commits data entered in account_window to the database"""

        self.account_window.hide()
        acc_name = self.gui.get_object('edit_acc_entry').get_text()
        credit = int(round(100 * self.gui.get_object('edit_acc_spinbutton').get_value()))
        if self.edit_acc_infos:
            if acc_name != self.edit_acc_infos[1]:
                self.db.set_account_name(self.edit_acc_infos[0], acc_name)
            if credit != 0:
                self.db.add_credit(self.edit_acc_infos[0], credit)
                self.show_credit_mail(acc_name, credit / 100.0)
        else:
            self.db.add_account(acc_name, credit)
        self.update_accounts_view()
        # TODO: reselect account after adding credit or select account after adding it
        self.account_window.destroy()

    def build_account_window(self):
        """Builds the account window and connects signals

        Drops following after being called for the second time 0_o
        Gtk-CRITICAL **: gtk_spin_button_get_adjustment:
            assertion `GTK_IS_SPIN_BUTTON (spin_button)' failed
        """

        self.gui.add_objects_from_file(BimiConfig.option('gui_path'),
                                       ['account_window', 'adjustment1'])
        self.account_window = self.gui.get_object('account_window')
        self.gui.connect_signals({'account_window_cancel': self.account_window_cancel,
                                  'account_window_save': self.account_window_save,
                                  'account_window_destroyed': self.account_window_destroyed})

    def build_drink_window(self):
        """Builds the drink window and connects signals

        No problems with gtk_spin_button_get_adjustment here, stupid gtk >_<
        """

        widgets = ['drink_window', 'adjustment2', 'adjustment3', 'adjustment4', 'adjustment5', 'adjustment6']
        self.gui.add_objects_from_file(BimiConfig.option('gui_path'), widgets)
        self.drink_window = self.gui.get_object('drink_window')
        self.gui.connect_signals({'drink_window_cancel': self.drink_window_cancel,
                                  'drink_window_save': self.drink_window_save,
                                  'drink_window_destroyed': self.drink_window_destroyed})

    def build_mail_window(self):
        self.gui.add_objects_from_file(BimiConfig.option('gui_path'), ['mail_window', 'mail_buffer'])
        self.mail_window = self.gui.get_object('mail_window')
        self.gui.connect_signals({'mail_window_destroyed': self.mail_window_destroyed})
        text_view = self.gui.get_object('mail_view')

        # NOTE: Gtk.Widget.modify_font is deprecated
        text_view.modify_font(Pango.FontDescription('monospace normal 10'))

    def consume_drinks(self, widget):
        lstore, it = self.accounts_view.get_selection().get_selected()
        if it is None:
            self._logger.info('No account selected, can\'t add drinks :(')
            return

        dids_amounts = []
        row_num = -1
        amount = 0
        for cbox, sbutton in self.drinks_comboxes_spinbuttons:
            row_num = cbox.get_active()
            amount = sbutton.get_value_as_int()
            if row_num != -1 and amount > 0:
                dids_amounts.append((self.drinks_list[(row_num, 0)][0], amount))

        self.db.consume_drinks(lstore.get_value(it, 0), dids_amounts)

        # Reset Spinbuttons
        for item in self.drinks_comboxes_spinbuttons:
            item[1].set_value(0)

        self.update_transactions_view(self.accounts_view)

    def delete_account(self, widget):
        row_num = self.accounts_view.get_path_at_pos(self.event_pos[0], self.event_pos[1])[0]
        self.db.del_account(self.accounts_list[(row_num, 0)][0])
        self.update_accounts_view()

    def delete_drink(self, widget):
        row_num = self.drinks_view.get_path_at_pos(self.event_pos[0], self.event_pos[1])[0]
        self.db.del_drink(self.drinks_list[(row_num, 0)][0])
        self.update_drinks_list()

    def undo_transaction(self, widget):
        row_num = self.transactions_view.get_path_at_pos(self.event_pos[0], self.event_pos[1])[0]
        self.db.undo_transaction(self.transactions_list[(row_num, 0)][0])
        self.update_transactions_view(self.accounts_view)

    def drinks_view_clicked(self, widget, event):
        if event.button == 3:
            self.event_pos = (event.x, event.y)
            if widget.get_path_at_pos(event.x, event.y) is None:
                self.gui.get_object('drinks_menu_edit').set_sensitive(False)
                self.gui.get_object('drinks_menu_delete').set_sensitive(False)
            else:
                self.gui.get_object('drinks_menu_edit').set_sensitive(True)
                self.gui.get_object('drinks_menu_delete').set_sensitive(True)
            self.drinks_context_menu.popup(None, None, None, None, event.button, event.time)

    def drink_window_cancel(self, widget):
        self.drink_window.destroy()

    def drink_window_destroyed(self, widget):
        self.drink_window = None
        self.edit_drink_infos = []

    def drink_window_save(self, widget):
        self.drink_window.hide()
        values = []
        values.append(self.gui.get_object('edit_drink_entry').get_text())
        for name in [f'edit_drink_spinbutton{i}' for i in (0, 1, 2)]:
            values.append(int(round(100 * self.gui.get_object(name).get_value())))
        values.append(self.gui.get_object('edit_drink_spinbutton3').get_value())
        values.append(self.gui.get_object('edit_drink_spinbutton4').get_value())
        values.append(True)

        if self.edit_drink_infos:
            self.db.set_drink(self.edit_drink_infos[0], values)
        else:
            self.db.add_drink(values)
        self.drink_window.destroy()
        self.update_drinks_list()

    def generate_credit_mail(self, account_name, credit):
        """Generates mail text from credit_mail option and database

        :param account_name: String containing the name of the account which recived the credit
        :param credit: Float containing the amount of added credit
        :return: Dictionary containing the 'body' and 'subject' strings of the credit mail
        """

        mail_body = BimiConfig.option('credit_mail_text') \
            .replace('$amount', str(credit) + BimiConfig.option('currency')) \
            .replace('$name', account_name)
        mail_subj = BimiConfig.option('credit_mail_subject') \
            .replace('$amount', str(credit) + BimiConfig.option('currency'))
        return {'body': mail_body, 'subject': mail_subj}

    def generate_summary_mail(self):
        """Generates mail text from summary_mail option and database

        :return: Dictionary containing the 'body' and 'subject' strings of the summary mail
        """

        mail_string = BimiConfig.option('summary_mail_text').split('\n')
        mail_body = ''
        for i, line in enumerate(mail_string):
            # substitute $kings in file with the kings information
            if line.find('$kings:') != -1:
                parts = list(line.partition('$kings:'))
                acc_drink_quaffed = self.db.kings()

                # Check if there are kings
                if acc_drink_quaffed:
                    len_acc = max(map(lambda x: len(x[0]), acc_drink_quaffed))
                    len_drink = max(map(lambda x: len(x[1]), acc_drink_quaffed))
                    len_quaffed = max(map(lambda x: len(str(x[2])), acc_drink_quaffed))
                    parts[2] = parts[2].replace('$name', '{name:<' + str(len_acc) + '}', 1)
                    parts[2] = parts[2].replace('$drink', '{drink:<' + str(len_drink) + '}', 1)
                    parts[2] = parts[2].replace('$amount', '{amount:>' + str(len_quaffed) + '}', 1)

                    for item in acc_drink_quaffed:
                        try:
                            insert = str(parts[0]) + \
                                     str(parts[2]).format(name=item[0],
                                                          drink=item[1],
                                                          amount=item[2])
                        except Exception as err:
                            self._logger.error('Line %s in file %s is not as expected! [err: %s]',
                                               str(i + 1), BimiConfig.option('mail_path'), err)
                            return
                        mail_body += insert + '\n'
                else:
                    mail_body += f'{parts[0]}The Rabble is delighted, there are no Kings and Queens!\n'

            # substitute $accInfos in file with the account informations
            elif line.find('$accInfos:') != -1:
                cur_symbol = BimiConfig.option('currency')
                parts = list(line.partition('$accInfos:'))

                accnames_balances = []
                for aid, name in self.db.accounts():
                    balance = sum(map(lambda x: x[2] * x[3], self.db.transactions(aid))) / \
                              100.0 - BimiConfig.option('deposit')
                    accnames_balances.append((name, balance))

                # Check if there are accounts in DB
                if accnames_balances:
                    len_acc = max(map(lambda x: len(x[0]), accnames_balances))
                    len_balance = max(map(lambda x: len(str(int(x[1]))), accnames_balances)) + 3  # +3 because .00
                    parts[2] = parts[2].replace('$name', '{name:<' + str(len_acc) + '}', 1)
                    parts[2] = parts[2].replace('$balance', '{balance:>' + str(len_balance)+'.2f}' + cur_symbol, 1)

                    for item in accnames_balances:
                        try:
                            insert = parts[0] + parts[2].format(name=item[0], balance=item[1])
                        except Exception as err:
                            self._logger.error('\'$accInfos:\' line in %s file is broken! [err: %s]',
                                               BimiConfig.option('mail_path'), err)
                            return
                        mail_body += insert + '\n'
                else:
                    mail_body += f'{parts[0]}No one lives in BimiTool-land ;_;\n'
            else:
                mail_body += line + '\n'

        return {'subject': BimiConfig.option('summary_mail_subject'), 'body': mail_body}

    def mail_window_destroyed(self, widget, stuff=None):
        self.mail_window = None

    def open_mail_program(self, mailto_dict):
        """Open mail program if option was selected

        Before opening the mail program in compose mode the strings in
        mailto_dict are converted mostly according to RFC 2368. The only
        difference is the character encoding with utf-8, which is not
        allowed in RFC 2368 but thunderbird supports it.

        :param mailto_dict: Dictionary containing 'to', 'body' and 'subject' strings
        :return: String containing the program name or None
        """

        mail_program = BimiConfig.option('mail_program')
        # Build mailto url from dictionary
        if mail_program is not None:
            if 'to' in mailto_dict:
                mailto_url = 'mailto:{}?'.format(urllib.parse.quote(mailto_dict['to'].encode('UTF-8')))
            else:
                mailto_url = 'mailto:?'
            if 'subject' in mailto_dict:
                mailto_url += 'subject={}&'.format(urllib.parse.quote(mailto_dict['subject'].encode('UTF-8')))
            if 'body' in mailto_dict:
                mailto_url += 'body={}'.format(urllib.parse.quote(mailto_dict['body'].encode('UTF-8')))
        else:
            return mail_program

        # Check which program to start
        if mail_program in {'icedove', 'thunderbird'}:
            process = subprocess.Popen([mail_program, '-compose', mailto_url], stdout=subprocess.PIPE)
            if process.communicate()[0] != '':
                self._logger.debug('%s: %s',
                                   mail_program, process.communicate()[0])
        return mail_program

    def pop_add_acc_window(self, widget):
        """Opens account_window"""

        if self.account_window is None:
            self.build_account_window()
        else:
            # TODO: Raise window
            pass
        self.account_window.set_title('Add account')
        self.gui.get_object('edit_acc_entry').set_text('Insert name')
        self.gui.get_object('edit_acc_entry').select_region(0, -1)
        self.gui.get_object('edit_acc_spinbutton').set_value(0.0)
        self.account_window.show()

    def pop_add_drink_window(self, widget):
        if self.drink_window is None:
            self.build_drink_window()
        else:
            # TODO: Raise window
            pass
        self.drink_window.set_title('Add drink')
        self.gui.get_object('edit_drink_entry').set_text('Insert name')
        self.gui.get_object('edit_drink_entry').select_region(0, -1)
        for i in range(5):
            self.gui.get_object('edit_drink_spinbutton' + str(i)).set_value(0)
        self.drink_window.show()

    def pop_edit_acc_window(self, widget):
        """Opens account_window and loads account infos"""

        if self.account_window is None:
            self.build_account_window()
        else:
            # TODO: Raise window
            pass
        self.account_window.set_title('Edit account')
        row_num = self.accounts_view.get_path_at_pos(self.event_pos[0], self.event_pos[1])[0]
        self.edit_acc_infos = self.accounts_list[(row_num,)]
        self.gui.get_object('edit_acc_entry').set_text(self.edit_acc_infos[1])
        self.gui.get_object('edit_acc_spinbutton').set_value(0.0)
        self.account_window.show()

    def pop_edit_drink_window(self, widget):
        if self.drink_window is None:
            self.build_drink_window()
        else:
            # TODO: Raise window
            pass
        self.drink_window.set_title('Edit drink')
        row_num = self.drinks_view.get_path_at_pos(self.event_pos[0], self.event_pos[1])[0]
        self.edit_drink_infos = self.drinks_list[(row_num,)]
        self.gui.get_object('edit_drink_entry').set_text(self.edit_drink_infos[1])
        cols = [2, 4, 6, 8, 9]
        for index, name in [(i, f'edit_drink_spinbutton{i}') for i in range(5)]:
            self.gui.get_object(name).set_value(self.edit_drink_infos[cols[index]])
        self.drink_window.show()

    def show_credit_mail(self, account_name, credit):
        """Open mail program in compose mode with credit_mail data

        :param account_name: String containig the name of the account holder
        :param credit: Float representing the amount of added credit
        :return:
        """

        mail_dict = self.generate_credit_mail(account_name, credit)
        self.open_mail_program(mail_dict)

    def show_summary_mail(self, widget):
        """Show summary mail in a gtk+ window or opens mail program

        size_request of scrolledwindow and textview doesn't work properly,
        which results in a too small window. stupid gtk
        """

        mail_dict = self.generate_summary_mail()
        if self.open_mail_program(mail_dict) is None:
            if self.mail_window is None:
                self.build_mail_window()
            else:
                # TODO: Raise window
                pass
            mail_buffer = self.gui.get_object('mail_buffer')
            mail_buffer.set_text(mail_dict['subject'] + '\n\n' + mail_dict['body'])
            self.mail_window.show_all()

    def tab_switched(self, widget, tab_child, activated_tab):
        if activated_tab == 1:
            self.update_drinks_list()

    def transactions_view_clicked(self, widget, event):
        if event.button == 3:
            self.event_pos = (event.x, event.y)
            if widget.get_path_at_pos(event.x, event.y) is not None:
                row_num = self.transactions_view.get_path_at_pos(event.x, event.y)[0]
                # Check if a transaction was clicked
                if self.transactions_list[(row_num, 0)][0] != -1:
                    self.gui.get_object('transactions_menu_delete').set_sensitive(True)
                    self.transactions_context_menu.popup(None, None, None, None, event.button, event.time)

    def update_accounts_view(self):
        """Loads accounts infos from database and updates accounts_list"""

        self.accounts_list.clear()
        db_account_list = self.db.accounts()
        for item in db_account_list:
            self.accounts_list.append(item)

    def update_drinks_combo_boxes(self):
        """Set active items for comboxes"""

        for index, drinks_comboxes_spinbutton in enumerate(self.drinks_comboxes_spinbuttons):
            if index < len(self.drinks_list):
                drinks_comboxes_spinbutton[0].set_active(index)

    def update_drinks_list(self):
        """Loads drink infos from database into drinks_list and updates
        widget dependent on drinks_list.
        """

        self.drinks_list.clear()
        cur_symbol = BimiConfig.option('currency')
        for item in self.db.drinks():
            self.drinks_list.append([item[0], item[1],
                                     item[2] / 100.0, str(item[2] / 100.0) + cur_symbol,
                                     item[3] / 100.0, str(item[3] / 100.0) + cur_symbol,
                                     item[4] / 100.0, str(item[4] / 100.0) + cur_symbol,
                                     item[5], item[6], item[7],
                                     item[1] + ' @ ' + str(item[2] / 100.0) + cur_symbol])
        self.update_drinks_combo_boxes()

    def update_transactions_view(self, widget):
        self.transactions_list.clear()
        lstore, it = self.accounts_view.get_selection().get_selected()
        if it is None:
            return
        self.transactions = self.db.transactions(lstore.get_value(it, 0))

        if self.transactions:
            # show only one row per transaction
            cur_symbol = BimiConfig.option('currency')
            total = 0.0
            tid_date_value = [self.transactions[0][0], str(self.transactions[0][4].date()), 0.0]
            for item in self.transactions:
                if tid_date_value[0] == item[0]:
                    tid_date_value[2] += item[3] / 100.0 * item[2]
                else:
                    tid_date_value[2] = str(tid_date_value[2]) + cur_symbol
                    self.transactions_list.append(tid_date_value)
                    tid_date_value[0] = item[0]
                    tid_date_value[1] = str(item[4].date())
                    tid_date_value[2] = item[3] / 100.0 * item[2]
                total += item[3] / 100.0 * item[2]
            tid_date_value[2] = str(tid_date_value[2]) + cur_symbol
            self.transactions_list.append(tid_date_value)
            if 0.009 < BimiConfig.option('deposit'):
                self.transactions_list.append([-1, 'Deposit', str(-BimiConfig.option('deposit')) + cur_symbol])
            self.transactions_list.append([-1, 'Balance', str(total - BimiConfig.option('deposit')) + cur_symbol])


if __name__ == '__main__':

    # Parse arguments
    parser = argparse.ArgumentParser(add_help=True,
                                     description='This program helps managing beverage consumation in dormitories')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        default=False,
                        dest='debug',
                        help='display debugging messages')
    parser.add_argument('--config',
                        default=None,
                        help='specify path to a config file',
                        type=str)
    parser.add_argument('--database',
                        default=None,
                        help='specify path to a sqlite data-base file',
                        type=str)
    options = parser.parse_args()

    # Initialize logger
    log_lvl = logging.ERROR
    if options.debug:
        log_lvl = logging.DEBUG
    logging.basicConfig(level=log_lvl,
                        format='%(asctime)s [%(levelname)8s] ' +
                               'Module %(name)s in line %(lineno)s %(funcName)s(): %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    # Setup config
    BimiConfig.load(options.config)
    if options.database is not None:
        BimiConfig.set_option('db_path', options.database)

    bmt = BiMiTool()
    Gtk.main()
