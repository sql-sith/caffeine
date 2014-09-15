# -*- coding: utf-8 -*-
#
# Copyright © 2009-2013 The Caffeine Developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


from gi.repository import GObject
import os
import os.path
import commands
import dbus

import applicationinstance
import caffeine
import utils
import logging

os.chdir(os.path.abspath(os.path.dirname(__file__)))


class Caffeine(GObject.GObject):

    def __init__(self):
        GObject.GObject.__init__(self)
        
        ## object to manage processes to activate for.
        self.ProcMan = caffeine.get_ProcManager()
        
        ## Status string.
        self.status_string = ""

        ## Makes sure that only one instance of Caffeine is run for
        ## each user on the system.
        self.pid_name = '/tmp/caffeine' + str(os.getuid()) + '.pid'
        self.appInstance = applicationinstance.ApplicationInstance( self.pid_name )

        ## In the next three list strings represent desktop enviroments in order:
        ## "KDE, GNOME and Unity", "Xfce and LXDE", "MATE".
        self.dbus_service = [
            'org.freedesktop.ScreenSaver',
            'org.freedesktop.PowerManagement',
            'org.mate.ScreenSaver'
        ]

        self.dbus_path = [
            '/ScreenSaver',
            '/org/freedesktop/PowerManagement/Inhibit',
            '/',
        ]

        self.dbus_interface = [
            'org.freedesktop.ScreenSaver',
            'org.freedesktop.PowerManagement.Inhibit',
            'org.mate.ScreenSaver',
        ]

        ## Number indicating what dbus service/path/interface to use.
        self.dbusType = None

	## This variable is set to a string describing only the type of screensaver
        ## used on this computer. Needed because users sometimes install additional
	## screensaver not from default instalation. It is detected when the user
        ## first attempts to inhibit the screensaver and powersaving. At the moment
	## only detects xscreensaver. Can be set to value: "XSS".
        self.screensaverType = None

        # Set to True when the detection routine is in progress
        self.attemptingToDetect = False

        self.dbusDetectionTimer = None
        self.dbusDetectionFailures = 0

        # Set to True when sleep seems to be prevented from the perspective of the user.
        # This does not necessarily mean that sleep really is prevented, because the
        # detection routine could be in progress.
        self.sleepAppearsPrevented = False

        # Set to True when sleep mode has been successfully inhibited somehow. This should
        # match up with "self.sleepAppearsPrevented" most of the time.
        self.sleepIsPrevented = False

        self.preventedForProcess = False
        self.dbusCookie = None
        self.xss_id = None

        ## check for processes to activate for.
        GObject.timeout_add(10000, self._check_for_process)
        
        print self.status_string


    def _check_for_process(self):
        activate = False
        for proc in self.ProcMan.get_process_list():
            if utils.isProcessRunning(proc):

                activate = True

                if self.preventedForProcess or not self.getActivated():
                    
                    logging.info("Caffeine has detected that the process '" + proc + "' is running, and will auto-activate")

                    self.setActivated(True)

                    self.preventedForProcess = True
                else:

                    logging.info("Caffeine has detected that the process '"+
                    proc + "' is running, but will NOT auto-activate"+
                    " as Caffeine has already been activated for a different"+
                    " reason.")


        ### No process in the list is running, deactivate.
        if not activate and self.preventedForProcess:
            logging.info("Caffeine had previously auto-activated for a process, but that process is no longer running; deactivating...")
            self.setActivated(False)

        return True

    def getActivated(self):
        return self.sleepIsPrevented

    def _deactivate(self):
        self.toggleActivated()

    
    def setActivated(self, activate):
        if self.getActivated() != activate:
            self.toggleActivated()

    def toggleActivated(self):
        """This function toggles the inhibition of the screensaver and powersaving
        features of the current computer."""

        self.preventedForProcess = False
        
        if self.sleepAppearsPrevented:
            self.sleepAppearsPrevented = False
            logging.info("Caffeine is now dormant; powersaving is re-enabled")
            self.status_string = _("Caffeine is dormant; powersaving is enabled")
        else:
            self.sleepAppearsPrevented = True

        self._performTogglingActions()

        if self.status_string == "":
            if self.dbusType != None:
                self.status_string = (_("Caffeine is preventing powersaving modes and screensaver activation"))
        
        self.emit("activation-toggled", self.getActivated(),
                self.status_string)
        self.status_string = ""

    def _detectDbusType(self):
        """This method always runs when the first attempt to inhibit the screensaver
        and powersaving is made. It detects what dbus service can be used.
        After detection is complete, it will finish the inhibiting process."""
        logging.info("Attempting to detect screensaver/powersaving type... (" + str(self.dbusDetectionFailures) + " dbus failures so far)")
        bus = dbus.SessionBus()

        if utils.isProcessRunning("xscreensaver"):
            self.screensaverType = "XSS"

        for i in xrange(len(self.dbus_service)):
            if self.dbusType == None and self.dbus_service[i] in bus.list_names():
                self.dbusType = i

        if self.dbusType == None:
            self.dbusDetectionFailures += 1
            if self.dbusDetectionFailures <= 3:
                self.dbusDetectionTimer = threading.Timer(10, self._detectDbusType)
                self.dbusDetectionTimer.start()
                return
            else:
                # Was unable to detect necessary dbus service.
                self.self.dbusType = False;

        self.attemptingToDetect = False
        self.dbusDetectionFailures = 0
        self.dbusDetectionTimer = None

        if self.dbusType == False:
            logging.info("Dbus detection was unsuccessful.")
        else:
            logging.info("Successfully detected dbus: " + str(self.dbus_service[self.dbusType]))

        if self.sleepAppearsPrevented != self.sleepIsPrevented:
            self._performTogglingActions()

    def _performTogglingActions(self):
        """This method performs the actions that affect the screensaver and powersaving."""
        if self.dbusType == None:
            if self.attemptingToDetect == False:
                self.attemptingToDetect = True
                self._detectDbusType()
            return

        if self.dbusType != False:
            # If necessary dbus service was detected.
            self._toggleDbus()

        if self.screensaverType == "XSS":
            self._toggleXSS()

        if self.sleepIsPrevented == False:
            logging.info("Caffeine is now preventing powersaving modes and screensaver activation")

        self.sleepIsPrevented = not self.sleepIsPrevented

    def _toggleDbus(self):
        """Toggle the screensaver and powersaving with dbus service."""

        bus = dbus.SessionBus()
        self.susuProxy = bus.get_object(self.dbus_service[self.dbusType], self.dbus_path[self.dbusType])
        self.iface = dbus.Interface(self.susuProxy, self.dbus_interface[self.dbusType])
        if self.sleepIsPrevented:
            if self.dbusCookie != None:
                self.iface.UnInhibit(self.dbusCookie)
        else:
            self.dbusCookie = self.iface.Inhibit('net.launchpad.caffeine', "User has requested that Caffeine disable the screen saver")

    def _toggleXSS(self):
        """Toggle the screensaver with xdg-screensaver (powersaving in most cases unaffected)"""

        if self.sleepIsPrevented:
            ### sleep prevention was on now turn it off
            # If the user clicks on the full coffee-cup to disable
            # sleep prevention, it should also
            # cancel the timer for timed activation.
            if self.xss_id != None:
                GObject.source_remove(self.xss_id)
        else:
            def deactivate():
                try:
                    output = commands.getoutput("xscreensaver-command -deactivate")
                except Exception, data:
                    logging.error("Exception occurred:\n" + data)
                return True
            # reset the idle timer every 50 seconds.
            self.xss_id = GObject.timeout_add(50000, deactivate)

## register a signal
GObject.signal_new("activation-toggled", Caffeine,
        GObject.SignalFlags.RUN_FIRST, None, [bool, str])
