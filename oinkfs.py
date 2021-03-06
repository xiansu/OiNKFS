#!/usr/bin/env python
#
#   This file is derived from an example file xmp.py by:
#                  2001  Jeff Epler  <jepler@unpythonic.dhs.org>
#                  2006  Csaba Henk  <csaba.henk@creo.hu>
#   Adding my name to the list: :)
#                  2012  Xian Su <xian.w.su@gmail.com>
#
#    This program can be distributed under the terms of the GNU GPL.
#    If you're a fucking weirdo, don't know about the GPL, and want to see it,
#    you can get a copy at http://www.gnu.org/licenses/gpl.txt
#

import os, sys
from errno import *
from stat import *
import fcntl

import fuse
from fuse import Fuse
import subprocess
import re
import ConfigParser
import time

if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."

fuse.fuse_python_api = (0, 2)

# We use a custom file class
fuse.feature_assert('stateful_files', 'has_init')

j = lambda *p: os.path.join(*p)

config = ConfigParser.ConfigParser()
config_file=j(os.path.expanduser('~'),'.oinkfs')
if os.path.isfile(config_file):
    config.read(config_file)
else:
    print "config file %s not found" % config_file
    sys.exit()

OINK_ROOT=config.get("oinkfs", "OINK_ROOT")
DEL_FILES=config.get("oinkfs", "DEL_FILES")


def flag2mode(flags):
    md = {os.O_RDONLY: 'r', os.O_WRONLY: 'w', os.O_RDWR: 'w+'}
    m = md[flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR)]

    if flags | os.O_APPEND:
        m = m.replace('w', 'a', 1)

    return m


class OiNKFS(Fuse):

    def __init__(self, *args, **kw):

        Fuse.__init__(self, *args, **kw)

        # do stuff to set up your filesystem here, if you want
        #import thread
        #thread.start_new_thread(self.mythread, ())
        self.root = OINK_ROOT
        self.file_class = self.OiNKFile

#    def mythread(self):
#
#        """
#        The beauty of the FUSE python implementation is that with the python interp
#        running in foreground, you can have threads
#        """
#        print "mythread: started"
#        while 1:
#            time.sleep(120)
#            print "mythread: ticking"

    def getattr(self, path):
        if os.path.isfile("." + path + ".slink"):
            return os.stat("." + path + ".slink")
        else:
            return os.lstat("." + path)

    def readlink(self, path):
        return os.readlink("." + path)

    def readdir(self, path, offset):
        for e in os.listdir("." + path):
            if e[-6:] != ".rdiff" and e[-6:] != ".slink":
                yield fuse.Direntry(e)

    def unlink(self, path):
        os.unlink("." + path)

    def rmdir(self, path):
        os.rmdir("." + path)

    def symlink(self, path, path1):
        os.symlink(path, "." + path1)

    def rename(self, path, path1):
        os.rename("." + path, "." + path1)

    def link(self, path, path1):
        os.link("." + path, "." + path1)

    def chmod(self, path, mode):
        os.chmod("." + path, mode)

    def chown(self, path, user, group):
        os.chown("." + path, user, group)

    def truncate(self, path, len):
        f = open("." + path, "a")
        f.truncate(len)
        f.close()

    def mknod(self, path, mode, dev):
        os.mknod("." + path, mode, dev)

    def mkdir(self, path, mode):
        os.mkdir("." + path, mode)

    def utime(self, path, times):
        os.utime("." + path, times)

#    The following utimens method would do the same as the above utime method.
#    We can't make it better though as the Python stdlib doesn't know of
#    subsecond preciseness in acces/modify times.
#  
#    def utimens(self, path, ts_acc, ts_mod):
#      os.utime("." + path, (ts_acc.tv_sec, ts_mod.tv_sec))

    def access(self, path, mode):
        if not os.access("." + path, mode):
            return -EACCES

#    This is how we could add stub extended attribute handlers...
#    (We can't have ones which aptly delegate requests to the underlying fs
#    because Python lacks a standard xattr interface.)
#
#    def getxattr(self, path, name, size):
#        val = name.swapcase() + '@' + path
#        if size == 0:
#            # We are asked for size of the value.
#            return len(val)
#        return val
#
#    def listxattr(self, path, size):
#        # We use the "user" namespace to please XFS utils
#        aa = ["user." + a for a in ("foo", "bar")]
#        if size == 0:
#            # We are asked for size of the attr list, ie. joint size of attrs
#            # plus null separators.
#            return len("".join(aa)) + len(aa)
#        return aa

    def statfs(self):
        """
        Should return an object with statvfs attributes (f_bsize, f_frsize...).
        Eg., the return value of os.statvfs() is such a thing (since py 2.2).
        If you are not reusing an existing statvfs object, start with
        fuse.StatVFS(), and define the attributes.

        To provide usable information (ie., you want sensible df(1)
        output, you are suggested to specify the following attributes:

            - f_bsize - preferred size of file blocks, in bytes
            - f_frsize - fundamental size of file blcoks, in bytes
                [if you have no idea, use the same as blocksize]
            - f_blocks - total number of blocks in the filesystem
            - f_bfree - number of free blocks
            - f_files - total number of file inodes
            - f_ffree - nunber of free file inodes
        """

        return os.statvfs(".")

    def fsinit(self):
        os.chdir(self.root)

    class OiNKFile(object):
        global DEL_FILES
        oinkfile_fullpath = ""
        oinkfile_difffile = ""
        oinkfile_smlnfile = ""
        oinkfile_tempfile = ""
        oinkfile_tempdirs = ""


        def __init__(self, path, flags, *mode):
            if not os.path.isdir("./tmp"):
                os.makedirs("./tmp")
            self.oinkfile_fullpath = "." + path
            self.oinkfile_difffile = "." + path + ".rdiff"
            self.oinkfile_smlnfile = "." + path + ".slink"

            log = open("./tmp/oinkfs.log",'a')

            if os.path.isfile(self.oinkfile_difffile):
                self.oinkfile_tempfile = "." + "/tmp" + path
                self.oinkfile_tempdirs = re.sub('[^/]*$', '', self.oinkfile_tempfile)
                if not os.path.isdir(self.oinkfile_tempdirs):
                    os.makedirs(self.oinkfile_tempdirs)

                if not os.path.isfile(self.oinkfile_tempfile):
                    log.write("%s accessing %s, creating %s\n" % (time.strftime('%Y/%m/%d %H:%M:%S'), self.oinkfile_fullpath, self.oinkfile_tempfile))
                    if not os.path.isfile(self.oinkfile_smlnfile):
                        patch = subprocess.Popen(['rdiff', 'patch', self.oinkfile_fullpath, self.oinkfile_difffile, self.oinkfile_tempfile], shell=False)
                    else:
                        patch = subprocess.Popen(['rdiff', 'patch', self.oinkfile_smlnfile, self.oinkfile_difffile, self.oinkfile_tempfile], shell=False)
                    patch.wait()
                else:
                    log.write("%s accessing %s, existing %s\n" % (time.strftime('%Y/%m/%d %H:%M:%S'), self.oinkfile_fullpath, self.oinkfile_tempfile))

                self.file = os.fdopen(os.open(self.oinkfile_tempfile, flags, *mode), flag2mode(flags))
                self.fd = self.file.fileno()
            else:
                if os.path.isfile(self.oinkfile_smlnfile):
                    log.write("%s accessing %s, following %s\n" % (time.strftime('%Y/%m/%d %H:%M:%S'), self.oinkfile_fullpath, self.oinkfile_smlnfile))
                    self.file = os.fdopen(os.open(self.oinkfile_smlnfile, flags, *mode), flag2mode(flags))
                    self.fd = self.file.fileno()
                else:
                    log.write("%s accessing %s, normal boring file\n" % (time.strftime('%Y/%m/%d %H:%M:%S'), self.oinkfile_fullpath))
                    self.file = os.fdopen(os.open(self.oinkfile_fullpath, flags, *mode), flag2mode(flags))
                    self.fd = self.file.fileno()

        def read(self, length, offset):
            self.file.seek(offset)
            return self.file.read(length)

        def write(self, buf, offset):
            self.file.seek(offset)
            self.file.write(buf)
            return len(buf)

        def release(self, flags):
            self.file.close()
            if DEL_FILES == "1":
                log = open("./tmp/oinkfs.log",'a')
                log.write("%s deleting %s\n" % (time.strftime('%Y/%m/%d %H:%M:%S'), self.oinkfile_tempfile))
                if os.path.isfile(self.oinkfile_tempfile):
                    os.remove(self.oinkfile_tempfile)

        def _fflush(self):
            if 'w' in self.file.mode or 'a' in self.file.mode:
                self.file.flush()

        def fsync(self, isfsyncfile):
            self._fflush()
            if isfsyncfile and hasattr(os, 'fdatasync'):
                os.fdatasync(self.fd)
            else:
                os.fsync(self.fd)

        def flush(self):
            self._fflush()
            os.close(os.dup(self.fd))

        def fgetattr(self):
            return os.fstat(self.fd)

        def ftruncate(self, len):
            self.file.truncate(len)

        def lock(self, cmd, owner, **kw):
            # The code here is much rather just a demonstration of the locking
            # API than something which actually was seen to be useful.

            # Advisory file locking is pretty messy in Unix, and the Python
            # interface to this doesn't make it better.
            # We can't do fcntl(2)/F_GETLK from Python in a platfrom independent
            # way. The following implementation *might* work under Linux. 
            #
            # if cmd == fcntl.F_GETLK:
            #     import struct
            # 
            #     lockdata = struct.pack('hhQQi', kw['l_type'], os.SEEK_SET,
            #                            kw['l_start'], kw['l_len'], kw['l_pid'])
            #     ld2 = fcntl.fcntl(self.fd, fcntl.F_GETLK, lockdata)
            #     flockfields = ('l_type', 'l_whence', 'l_start', 'l_len', 'l_pid')
            #     uld2 = struct.unpack('hhQQi', ld2)
            #     res = {}
            #     for i in xrange(len(uld2)):
            #          res[flockfields[i]] = uld2[i]
            #  
            #     return fuse.Flock(**res)

            # Convert fcntl-ish lock parameters to Python's weird
            # lockf(3)/flock(2) medley locking API...
            op = { fcntl.F_UNLCK : fcntl.LOCK_UN,
                   fcntl.F_RDLCK : fcntl.LOCK_SH,
                   fcntl.F_WRLCK : fcntl.LOCK_EX }[kw['l_type']]
            if cmd == fcntl.F_GETLK:
                return -EOPNOTSUPP
            elif cmd == fcntl.F_SETLK:
                if op != fcntl.LOCK_UN:
                    op |= fcntl.LOCK_NB
            elif cmd == fcntl.F_SETLKW:
                pass
            else:
                return -EINVAL

            fcntl.lockf(self.fd, op, kw['l_start'], kw['l_len'])



def main():

    usage = """
Userspace nullfs-alike: mirror the filesystem tree from some point on.

""" + Fuse.fusage

    server = OiNKFS(version="%prog " + fuse.__version__,
                 usage=usage)

    server.multithreaded = False


    server.parse(values=server, errex=1)

    try:
        if server.fuse_args.mount_expected():
            os.chdir(server.root)
    except OSError:
        print >> sys.stderr, "can't enter root of underlying filesystem"
        sys.exit(1)

    server.main()


if __name__ == '__main__':
    main()
