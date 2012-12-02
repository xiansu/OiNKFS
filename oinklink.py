#!/usr/bin/env python
#
#   This file is created by:
#                  Xian Su <xian.w.su@gmail.com>
#
#    This program can be distributed under the terms of the GNU GPL.
#    If you're a fucking weirdo, don't know about the GPL, and want to see it,
#    you can get a copy at http://www.gnu.org/licenses/gpl.txt
#

import sys
import os
import io
import subprocess
import hashlib
import re
import ConfigParser
import time
import locale
import shutil
from collections import deque
locale.setlocale(locale.LC_ALL, '')

j = lambda *p: os.path.join(*p)

config = ConfigParser.ConfigParser()
config_file=j(os.path.expanduser('~'),'.oinkfs')
if os.path.isfile(config_file):
    try:
        config.read(config_file)
    except ConfigParser.ParsingError:
        print bcolors.red + "your config file contains an error: most likely you're missing a space in front of an added perm_root dir" + bcolors.none
        print sys.exc_info()[1]
else:
    print "config file %s not found" % config_file
    sys.exit()

PERM_ROOT=unicode(config.get("oinklink", "PERM_ROOT"))
ORIG_ROOT=unicode(config.get("oinklink", "ORIG_ROOT"))
LINK_ROOT=unicode(config.get("oinklink", "LINK_ROOT"))

PERM_ROOT=PERM_ROOT.split("\n")

total_number_of_album_directories = 0
total_number_of_directories_to_mk = 0
total_number_of_match_music_files = 0
total_number_of_total_music_files = 0
total_number_of_match_other_files = 0
total_number_of_total_other_files = 0
total_size_of_match_music_files = 0
total_size_of_total_music_files = 0
total_size_of_match_other_files = 0
total_size_of_total_other_files = 0


class Album:
    album = u""
    tracker = u""
    orig_path = u""
    perm_path = u""
    link_path = u""
    need_link = u""

    def __init__(self, album, tracker):
        self.orig_log_files = []
        self.orig_rip_times = []
        self.perm_log_files = []
        self.perm_rip_times = []

        self.album = album.encode('utf-8')
        self.tracker = tracker.encode('utf-8')

        self.orig_path = j(ORIG_ROOT, tracker, album)
        self.link_path = j(LINK_ROOT, tracker, album)

        for perm_root in PERM_ROOT:
            self.perm_path = j(perm_root, album)
            del self.orig_log_files[:]
            del self.orig_rip_times[:]
            del self.perm_log_files[:]
            del self.perm_rip_times[:]

            if os.path.isdir(self.perm_path) and (not os.path.isdir(self.link_path) or os.path.islink(self.link_path)):
                for root, dirs, files in os.walk(self.orig_path):
                    for file in files:
                        if file[-4:].lower() == ".log":
                            self.orig_log_files.append(j(root,file).encode('utf-8'))
                for log in self.orig_log_files:
                    c = len(self.orig_rip_times)
                    for line in open(log,'r'):
                        if "extraction logfile" in line:
                            self.orig_rip_times.append(line)

                    if c == len(self.orig_rip_times):
                        try:
                            for line in io.open(log,'r',encoding='utf-16'):
                                if "extraction logfile" in line:
                                    self.orig_rip_times.append(line)
                        except UnicodeError:
                            pass
#                           print "couldn't find extraction time for %s in utf-8 and file is not utf-16" %log

                    if c == len(self.orig_rip_times):
                        print "error reading riptime from %s" % log

                for root, dirs, files in os.walk(self.perm_path):
                    for file in files:
                        if file[-4:].lower() == ".log":
                            self.perm_log_files.append(j(root,file).encode('utf-8'))

                for log in self.perm_log_files:
                    c = len(self.perm_rip_times)
                    for line in open(log,'r'):
                        if "extraction logfile" in line:
                            self.perm_rip_times.append(line)
                    if c == len(self.perm_rip_times):
                        try:
                            for line in io.open(log,'r',encoding='utf-16'):
                                if "extraction logfile" in line:
                                    self.perm_rip_times.append(line)
                        except UnicodeError:
                            pass
#                           print "couldn't find extraction time for %s in utf-8 and file is not utf-16" %log

                    if c == len(self.perm_rip_times):
                        print "error reading riptime from %s" % log

                if sorted(set(self.orig_rip_times)) == sorted(set(self.perm_rip_times)):
# UNCOMMENT ALL THESE LINES IF YOU WANT TO MIRROR ORIG_ROOT WITH SYMLINKS
#                   if os.path.islink(self.link_path):
#                       print "match found for %s but %s exists, so removing link" % (self.orig_path, self.link_path)
#                       os.unlink(self.link_path)
                    self.need_link = True
                    break
#       if not self.need_link and not os.path.isdir(self.link_path):
#           dircheck=re.sub('[^/]*$', '', self.link_path)
#           print "symlinking %s since %s doesn't exist and no matches were found" % (self.orig_path, self.link_path)
#           if not os.path.isdir(dircheck):
#               os.makedirs(dircheck)
#           os.symlink(self.orig_path, self.link_path)

    def __unicode__(self):
        return "%s" % (self.orig_path)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __eq__(self, b):
        return self.orig_path == b.orig_path

    def __cmp__(self, b):
        if self.orig_path == b.orig_path: return 0
        if self.orig_path < b.orig_path: return -1
        if self.orig_path > b.orig_path: return 1

    def __hash__(self):
        return hash(self.orig_path)

    def walk_album(self):
        self.orig_dirs = []
        self.orig_files = []
        self.perm_dirs = []
        self.perm_files = []
        self.link_dirs = []

        for root, dirs, files in os.walk(self.orig_path):
            for dir in dirs:
                self.orig_dirs.append(j(root,dir).encode('utf-8'))
            for file in files:
                self.orig_files.append(Track(j(root,file).encode('utf-8'), file))
        for root, dirs, files in os.walk(self.perm_path):
            for dir in dirs:
                self.perm_dirs.append(j(root,dir).encode('utf-8'))
            for file in files:
                self.perm_files.append(Track(j(root,file).encode('utf-8'), file))

        self.orig_dirs.sort()
        self.orig_files.sort()
        self.perm_dirs.sort()
        self.perm_files.sort()
        return True

    def pick_track(self):
        def binary_bytes(bytes):
            if bytes > 1073741823:
                return str("%.2f" % (float(bytes)/1073741824)) + "GB"
            elif bytes > 1048575:
                return str("%.2f" % (float(bytes)/1048576)) + "MB"
            elif bytes > 1023:
                return str("%.2f" % (float(bytes)/1024)) + "KB"
            else:
                return str(bytes) + "B"
            
        global total_number_of_album_directories
        global total_number_of_directories_to_mk
        global total_number_of_match_music_files
        global total_number_of_total_music_files
        global total_number_of_match_other_files
        global total_number_of_total_other_files
        global total_size_of_match_music_files
        global total_size_of_total_music_files
        global total_size_of_match_other_files
        global total_size_of_total_other_files

        album_number_of_album_directories = 0
        album_number_of_directories_to_mk = 0
        album_number_of_match_music_files = 0
        album_number_of_total_music_files = 0
        album_number_of_match_other_files = 0
        album_number_of_total_other_files = 0
        album_size_of_match_music_files = 0
        album_size_of_total_music_files = 0
        album_size_of_match_other_files = 0
        album_size_of_total_other_files = 0

        print bcolors.cyan + "[%s]" % self.link_path + bcolors.none
        album_number_of_album_directories += 1
        album_number_of_directories_to_mk += 1

        self.link_dirs.append(self.link_path)

        for orig_dir in self.orig_dirs:
            self.link_dirs.append(orig_dir.replace(ORIG_ROOT, LINK_ROOT, 1))
            print bcolors.cyan + "[%s]" % orig_dir.replace(ORIG_ROOT, LINK_ROOT, 1) + bcolors.none
            album_number_of_directories_to_mk += 1

        for orig_track in self.orig_files:
            if is_song(orig_track.filename):
                album_number_of_total_music_files += 1
                album_size_of_total_music_files += orig_track.size
            else:
                album_number_of_total_other_files += 1
                album_size_of_total_other_files += orig_track.size

            for perm_track in self.perm_files:
                if is_song(orig_track.filename):
                    if perm_track.md5 == orig_track.md5:
                        if len(perm_track.possible_track_positions) == 1 and len(orig_track.possible_track_positions) == 1 and perm_track.possible_track_positions.values() == orig_track.possible_track_positions.values():
                            orig_track.match = perm_track.fullpath
                            album_number_of_match_music_files += 1
                            album_size_of_match_music_files += perm_track.size
                            break
                        else:
                            orig_track.possible_matches.append(perm_track)

                else:
                    if perm_track.md5 == orig_track.md5:
                        orig_track.match = perm_track.fullpath
                        album_number_of_match_other_files += 1
                        album_size_of_match_other_files += perm_track.size
            if not orig_track.match and orig_track.possible_matches:
                for perm_track in orig_track.possible_matches:
                    if 0 in perm_track.possible_track_positions.values() and perm_track.possible_track_positions[0] in orig_track.possible_track_positions.values():
                        orig_track.match = perm_track.fullpath
                        album_number_of_match_music_files += 1
                        album_size_of_match_music_files += perm_track.size
                        break

            if not orig_track.match and orig_track.possible_matches:
                orig_track.match = orig_track.possible_matches[0].fullpath
                album_number_of_match_music_files += 1
                album_size_of_match_music_files += orig_track.possible_matches[0].size

            if orig_track.match:
                print bcolors.green + "%s" % orig_track.match + bcolors.blue + " -> %s" % orig_track.linkfile + bcolors.none
            else:
                print bcolors.red + "%s" % orig_track.fullpath + bcolors.blue + " -> %s" % orig_track.linkfile + bcolors.none

        total_number_of_album_directories += album_number_of_album_directories
        total_number_of_directories_to_mk += album_number_of_directories_to_mk
        total_number_of_match_music_files += album_number_of_match_music_files
        total_number_of_total_music_files += album_number_of_total_music_files
        total_number_of_match_other_files += album_number_of_match_other_files
        total_number_of_total_other_files += album_number_of_total_other_files
        total_size_of_match_music_files += album_size_of_match_music_files
        total_size_of_total_music_files += album_size_of_total_music_files
        total_size_of_match_other_files += album_size_of_match_other_files
        total_size_of_total_other_files += album_size_of_total_other_files

        print "ALBUM: [ dirs: %d/%d ] [ music: %d/%d (%s/%s:%d%%) ] [ other: %d/%d (%s/%s:%d%%) ]" % (album_number_of_album_directories, album_number_of_directories_to_mk, album_number_of_match_music_files, album_number_of_total_music_files, locale.format("%d", album_size_of_match_music_files, grouping=True), locale.format("%d", album_size_of_total_music_files, grouping=True), (100*album_size_of_match_music_files/album_size_of_total_music_files), album_number_of_match_other_files, album_number_of_total_other_files, locale.format("%d", album_size_of_match_other_files, grouping=True), locale.format("%d", album_size_of_total_other_files, grouping=True), (100*album_size_of_match_other_files/album_size_of_total_other_files))

        print "TOTAL: [ dirs: %d/%d ] [ music: %d/%d (%s/%s:%d%%) ] [ other: %d/%d (%s/%s:%d%%) ]" % (total_number_of_album_directories, total_number_of_directories_to_mk, total_number_of_match_music_files, total_number_of_total_music_files, binary_bytes(total_size_of_match_music_files), binary_bytes(total_size_of_total_music_files), (100*total_size_of_match_music_files/total_size_of_total_music_files), total_number_of_match_other_files, total_number_of_total_other_files, binary_bytes(total_size_of_match_other_files), binary_bytes(total_size_of_total_other_files), (100*total_size_of_match_other_files/total_size_of_total_other_files))
        return True

    def link_track(self):
        for link_dir in self.link_dirs:
            if not os.path.isdir(link_dir):
                os.makedirs(link_dir)
        for orig_file in self.orig_files:
            if not os.path.isfile(orig_file.linkfile):
                if orig_file.match:
                    try:
                        os.link(orig_file.match, orig_file.linkfile)
                    except OSError:
                        if sys.exc_info()[1].errno == 18:
#                           print bcolors.yellow + "could not create hardlink, creating sym link instead: " + bcolors.green + "%s " % orig_file.match + bcolors.blue + "-> %s" % orig_file.linkfile + bcolors.none
                            os.symlink(orig_file.match, orig_file.linkfile+".slink")
                            padding = open(orig_file.linkfile, 'a')
                            padding.write("%s" % orig_file.size)
                else:
                    try:
                        os.link(orig_file.fullpath, orig_file.linkfile)
                    except OSError:
                        if sys.exc_info()[1].errno == 18:
#                           print bcolors.yellow + "could not create hardlink, copying file over instead: " + bcolors.red + "%s " % orig_file.fullpath + bcolors.blue + "-> %s" % orig_file.linkfile + bcolors.none
                            shutil.copyfile(orig_file.fullpath, orig_file.linkfile)
        return True

    def diff_track(self):
        sig_procs = []
        delta_procs = []
        def sig(match, sig):
            sig_procs.append(subprocess.Popen(['rdiff','signature', match, sig], shell=False))
        def delta(sig, orig, rdiff):
            delta_procs.append(subprocess.Popen(['rdiff','delta', sig, orig, rdiff], shell=False))

        matching_music_tracks = []
        for orig_file in self.orig_files:
            if orig_file.match and is_song(orig_file.filename):
                matching_music_tracks.append(orig_file)

        for track in matching_music_tracks:
            sig(track.match, track.linkfile + ".sig")
        for sig_proc in sig_procs:
            sig_proc.wait()
        for track in matching_music_tracks:
            delta(track.linkfile + ".sig", track.fullpath, track.linkfile + ".rdiff")
        for delta_proc in delta_procs:
            delta_proc.wait()
        for track in matching_music_tracks:
            if os.path.isfile(track.linkfile + ".sig"):
                os.remove(track.linkfile + ".sig")
        print "finished diffing album: %s" % self.album
        return True

class Track:
    fullpath = ""
    filename = ""
    size = ""
    md5 = ""
    linkfile = ""
    match = ""

    def __init__(self, fullpath, filename):
        self.possible_track_positions = dict()
        self.possible_matches = []
        self.fullpath = fullpath
        self.linkfile = self.fullpath.replace(ORIG_ROOT.encode('utf-8'), LINK_ROOT.encode('utf-8'), 1)
        self.filename = filename
        self.size = os.path.getsize(fullpath)
        if is_song(filename):
            for tpos in re.finditer(r'(?=(\d{2}))', filename):
                self.possible_track_positions[tpos.start()]=tpos.group(1)
#               for tpos in re.finditer(r'(?=(\d{2})[^\w])', filename):
#                   self.possible_track_positions.append(tpos)
                # use .start(), .start()+1 and .group(1)
            self.md5 = md5song(fullpath)
        else:
            self.md5 = md5(fullpath)

    def __cmp__(self, b):
        if self.fullpath == b.fullpath: return 0
        if self.fullpath < b.fullpath: return -1
        if self.fullpath > b.fullpath: return 1

    def __eq__(self, b):
        return self.md5 == b.md5

    def __str__(self):
        return self.fullpath

class bcolors:
    red = '\033[31m'
    green = '\033[32m'
    yellow = '\033[33m'
    blue = '\033[34m'
    cyan = '\033[36m'
    none = '\033[0m'

def md5song(file):
    f = open(file, 'rb')
    flac = deque([],4)
    fLaC = deque(['f','L','a','C'])
    while flac != fLaC:
        flac.append(f.read(1))
    f.seek(22,1)
    return f.read(16).encode('hex_codec')

def md5(file):
    f = open(file, 'rb')
    m = hashlib.md5()
    while True:
        data = f.read(8192)
        if not data:
            break
        m.update(data)
    return m.hexdigest()

def is_song(filename):
    return filename.lower().endswith('.flac')

def find_albums():
    albums = []
    for tracker in os.listdir(ORIG_ROOT):
        r = j(ORIG_ROOT, tracker)
        if os.path.isdir(r) and tracker != "torrents":
            for album in os.listdir(r):
                albums.append(Album(album, tracker))
    return albums

def walk_albums(albums):
    for album in albums:
        album.walk_album()
    return True

def pick_tracks(albums):
    for album in albums:
        album.pick_track()
    return True

def link_tracks(albums):
    for album in albums:
        album.link_track()
    return True

def diff_tracks(albums):
    for album in albums:
        album.diff_track()
    return True

def main():
    albums = find_albums()
    print "number of albums found in path: %d" % len(albums)
    albums[:] = [album for album in albums if album.need_link]
    albums.sort()
    print "number of matches with library: %d" % len(albums)
    if not albums:
        sys.exit()

    walk_albums(albums)
    pick_tracks(albums)
    print "\nLinking files in 10 seconds. Press Ctrl-C to abort."
    for wtf in range(10, -1, -1):
        if wtf < 4:
            print wtf
        time.sleep(1)

    link_tracks(albums)
    diff_tracks(albums)

if __name__ == "__main__":
    sys.exit(main())
