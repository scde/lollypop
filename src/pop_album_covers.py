#!/usr/bin/python
# Copyright (c) 2014-2015 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, GLib, Gio, GdkPixbuf

import urllib.request
import urllib.parse
from _thread import start_new_thread
from gettext import gettext as _

from lollypop.define import Lp, ArtSize, GOOGLE_INC, GOOGLE_MAX
from lollypop.view_container import ViewContainer

# Show a popover with album covers from the web
class PopAlbumCovers(Gtk.Popover):

    """
        Init Popover ui with a text entry and a scrolled treeview
        @param artist id as int
        @param album id as int
    """
    def __init__(self, artist_id, album_id):
        Gtk.Popover.__init__(self)
        self._album_id = album_id
        self._start = 0
        self._orig_pixbufs = {}

        album = Lp.albums.get_name(album_id)
        artist = Lp.artists.get_name(artist_id)

        self._search = "%s+%s" % (artist, album)

        self._stack = Gtk.Stack()
        self._stack.show()

        builder = Gtk.Builder()
        builder.add_from_resource(
                    '/org/gnome/Lollypop/PopAlbumCovers.ui')

        widget = builder.get_object('widget')
        widget.add(self._stack)

        self._view = Gtk.FlowBox()
        self._view.set_selection_mode(Gtk.SelectionMode.NONE)
        self._view.connect('child-activated', self._on_activate)
        self._view.set_max_children_per_line(100)
        self._view.set_property('row-spacing', 10)
        self._view.show()

        self._label = builder.get_object('label')
        self._label.set_text(_("Please wait..."))

        builder.get_object('viewport').add(self._view)

        self._scrolled = builder.get_object('scrolled')
        spinner = builder.get_object('spinner')
        self._not_found = builder.get_object('notfound')
        self._stack.add(spinner)
        self._stack.add(self._not_found)
        self._stack.add(self._scrolled)
        self._stack.set_visible_child(spinner)
        self.add(widget)

    """
        Populate view
    """
    def populate(self):
        self._thread = True
        start_new_thread(self._populate, ())

    """
        Resize popover and set signals callback
    """
    def do_show(self):
        self.set_size_request(700, 400)
        Gtk.Popover.do_show(self)

    """
        Kill thread
    """
    def do_hide(self):
        self._thread = False
        Gtk.Popover.do_hide(self)

#######################
# PRIVATE             #
#######################
    """
        Same as populate()
    """
    def _populate(self):
        self._urls = []
        if Gio.NetworkMonitor.get_default().get_network_available():
            self._urls = Lp.art.get_google_arts(self._search)
        if self._urls:
            self._start += GOOGLE_INC
            self._add_pixbufs()
        else:
            GLib.idle_add(self._show_not_found)

    """
        Add urls to the view
        #FIXME Do not use recursion
    """
    def _add_pixbufs(self):
        if self._urls:
            url = self._urls.pop()
            stream = None
            try:
                response = urllib.request.urlopen(url)
                stream = Gio.MemoryInputStream.new_from_data(
                                                response.read(), None)
            except:
                if self._thread:
                    self._add_pixbufs()
            if stream:
                GLib.idle_add(self._add_pixbuf, stream)
            if self._thread:
                self._add_pixbufs()
        elif self._start < GOOGLE_MAX:
            self._populate()

    """
        Show not found message
    """
    def _show_not_found(self):
        if len(self._view.get_children()) == 0:
            self._label.set_text(_("No cover found..."))
            self._stack.set_visible_child(self._not_found)

    """
        Add stream to the view
    """
    def _add_pixbuf(self, stream):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                                            stream, ArtSize.MONSTER,
                                            ArtSize.MONSTER,
                                            False,
                                            None)
            image = Gtk.Image()
            self._orig_pixbufs[image] = pixbuf
            scaled_pixbuf = pixbuf.scale_simple(ArtSize.BIG,
                                                      ArtSize.BIG,
                                                      2)
            image.set_from_pixbuf(scaled_pixbuf)
            del scaled_pixbuf
            del pixbuf
            image.show()
            self._view.add(image)
        except Exception as e:
            print(e)
            pass
        # Remove spinner if exist
        if self._scrolled != self._stack.get_visible_child():
            self._label.set_text(_("Select a cover art for this album"))
            self._stack.set_visible_child(self._scrolled)

    """
        Use pixbuf as cover
        Reset cache and use player object to announce cover change
    """
    def _on_activate(self, flowbox, child):
        pixbuf = self._orig_pixbufs[child.get_child()]
        Lp.art.save_album_art(pixbuf, self._album_id)
        Lp.art.clean_album_cache(self._album_id)
        Lp.art.announce_cover_update(self._album_id)
        self.hide()
        self._streams = {}
