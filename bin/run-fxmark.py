#!/usr/bin/env python3
import os
import sys
import signal
import subprocess
import datetime
import tempfile
import pdb
from os.path import join
from perfmon import PerfMon

CUR_DIR = os.path.abspath(os.path.dirname(__file__))

try:
    import cpupol
except ImportError:
    print("No cpupolicy for this machine.")
    print("Do \'make\' at %s\n"
          % os.path.normpath(os.path.join(CUR_DIR, "..")))
    raise

def catch_ctrl_C(sig, frame):
    print("Umount a testing file system. Please wait.")

class Runner(object):
    # media path
    LOOPDEV = "/dev/loop1"
    NVMEDEV = "/dev/nvme1n1p1"
    HDDDEV  = "/dev/mdxxx"
    SSDDEV  = "/dev/md0p1"

    # test core granularity
    CORE_FINE_GRAIN   = 1
    CORE_COARSE_GRAIN = 0

    def __init__(self, \
                 core_grain = CORE_COARSE_GRAIN, \
                 pfm_lvl = PerfMon.LEVEL_LOW, \
                 # run_filter = ("nvme", "*", "DRBL", "*", "directio")):
                 # ("mem", "*", "DWOL", "80", "directio")),
                 run_filter = ("*", "*", "*", "*", "*")):

        # run config
        self.CORE_GRAIN    = core_grain
        self.PERFMON_LEVEL = pfm_lvl
        self.FILTER        = run_filter # media, fs, bench, ncore, directio
        self.DRYRUN        = False
        self.DEBUG_OUT     = True

        # bench config
        self.DISK_SIZE     = "30G"
        self.DURATION      = 30 # seconds
        # self.DIRECTIOS     = ["bufferedio", "directio"]  # enable directio except tmpfs -> nodirectio
        self.DIRECTIOS     = [ str(IO_TYPE_CFG_ARG) ]
        # self.MEDIA_TYPES   = ["ssd", "hdd", "nvme", "mem"]
        # XXX: MEDIA_TYPES receives from arguments now
        self.MEDIA_TYPES = [MEDIA_TYPE_CFG_ARG]
        #self.FS_TYPES      = ["tmpfs", "ext4", "ext4_no_jnl", "f2fs",
        self.FS_TYPES      = ["ext4",
                              # "xfs", "btrfs", "jfs", "reiserfs", "ext2", "ext3",
        ]
        self.BENCH_TYPES   = [
            # write/write
            "DWOL",
            "DWOM",
            "DWAL",
            "DWTL",
            "DWSL",
            "MWCL",
            "MWCM",
            "MWUL",
            "MWUM",
            "MWRL",
            "MWRM",

            # filebench
            # "filebench_varmail",
            # "filebench_oltp",
            # "filebench_fileserver",

            # dbench
            # "dbench_client",

            # read/read

            "DRBL",
            "DRBM",
            "DRBH",

            "MRPL",
            "MRPM",
            "MRPH",
            "MRDL",
            "MRDM",

            # read/write
            # "MRPM_bg",
            # "DRBM_bg",
            # "MRDM_bg",
            # "DRBH_bg",
            # "DRBL_bg",
            # "MRDL_bg",
        ]
        self.BENCH_BG_SFX   = "_bg"

        # path config
        self.ROOT_NAME      = "root"
        self.LOGD_NAME      = "../logs"
        self.FXMARK_NAME    = "fxmark"
        self.FILEBENCH_NAME = "run-filebench.py"
        self.DBENCH_NAME    = "run-dbench.py"
        self.PERFMN_NAME    = "perfmon.py"

        # fs config
        self.HOWTO_MOUNT = {
            "tmpfs":self.mount_tmpfs,
            "ext2":self.mount_anyfs,
            "ext3":self.mount_anyfs,
            "ext4":self.mount_anyfs,
            "ext4_no_jnl":self.mount_ext4_no_jnl,
            "xfs":self.mount_anyfs,
            "btrfs":self.mount_anyfs,
            "f2fs":self.mount_anyfs,
            "jfs":self.mount_anyfs,
            "reiserfs":self.mount_anyfs,
        }
        self.HOWTO_MKFS = {
            "ext2":"-F",
            "ext3":"-F",
            "ext4":"-F",
            "ext4_no_jnl":"-F",
            "xfs":"-f",
            "btrfs":"-f",
            "jfs":"-q",
            "reiserfs":"-q",
        }

        # media config
        self.HOWTO_INIT_MEDIA = {
            "mem":self.init_mem_disk,
            "nvme":self.init_nvme_disk,
            "ssd":self.init_ssd_disk,
            "hdd":self.init_hdd_disk,
        }

        # misc. setup
        self.redirect    = subprocess.PIPE if not self.DEBUG_OUT else None
        self.dev_null    = open("/dev/null", "a") if not self.DEBUG_OUT else None
        self.npcpu       = cpupol.PHYSICAL_CHIPS * cpupol.CORE_PER_CHIP
        self.nhwthr      = self.npcpu * cpupol.SMT_LEVEL
        self.ncores      = self.get_ncores()
        self.test_root   = os.path.normpath(
            os.path.join(CUR_DIR, self.ROOT_NAME))
        self.fxmark_path = os.path.normpath(
            os.path.join(CUR_DIR, self.FXMARK_NAME))
        self.filebench_path = os.path.normpath(
            os.path.join(CUR_DIR, self.FILEBENCH_NAME))
        self.dbench_path = os.path.normpath(
            os.path.join(CUR_DIR, self.DBENCH_NAME))
        self.tmp_path = os.path.normpath(
        # XXX: changed to point to the RAMDISK
            #os.path.join(CUR_DIR, ".tmp"))
            os.path.join(RAMDISK_PATH_CFG_ARG, ".tmp"))
        self.disk_path = os.path.normpath(
            os.path.join(self.tmp_path, "disk.img"))

        self.perfmon_start = "%s start" % os.path.normpath(
            os.path.join(CUR_DIR, self.PERFMN_NAME))
        self.perfmon_stop = "%s stop" % os.path.normpath(
            os.path.join(CUR_DIR, self.PERFMN_NAME))
        self.perfmon_log = ""
        self.log_dir     = ""
        self.log_path    = ""
        self.umount_hook = []
        self.active_ncore = -1

    def log_start(self):
        self.log_dir = os.path.normpath(
            os.path.join(CUR_DIR, self.LOGD_NAME,
                         str(datetime.datetime.now()).replace(' ','-').replace(':','-')))
        self.log_path = os.path.normpath( os.path.join(self.log_dir, "fxmark.log"))
        self.exec_cmd("mkdir -p " + self.log_dir, self.dev_null)

        self.log_fd = open(self.log_path, "bw")
        p = self.exec_cmd("echo -n \"### SYSTEM         = \"; uname -a", self.redirect)
        if self.redirect:
            for l in p.stdout.readlines():
                self.log(l.decode("utf-8").strip())
        self.log("### DISK_SIZE      = %s"   % self.DISK_SIZE)
        self.log("### DURATION       = %ss"  % self.DURATION)
        self.log("### DIRECTIO       = %s"   % ','.join(self.DIRECTIOS))
        self.log("### MEDIA_TYPES    = %s"   % ','.join(self.MEDIA_TYPES))
        self.log("### FS_TYPES       = %s"   % ','.join(self.FS_TYPES))
        self.log("### BENCH_TYPES    = %s"   % ','.join(self.BENCH_TYPES))
        self.log("### NCORES         = %s"   %
                 ','.join(map(lambda c: str(c), self.ncores)))
        self.log("### CORE_SEQ       = %s" %
                 ','.join(map(lambda c: str(c), cpupol.seq_cores)))
        self.log("\n")
        self.log("### MODEL_NAME     = %s" % cpupol.MODEL_NAME)
        self.log("### PHYSICAL_CHIPS = %s" % cpupol.PHYSICAL_CHIPS)
        self.log("### CORE_PER_CHIP  = %s" % cpupol.CORE_PER_CHIP)
        self.log("### SMT_LEVEL      = %s" % cpupol.SMT_LEVEL)
        self.log("\n")

    def log_end(self):
        self.log_fd.close()

    def log(self, log):
        self.log_fd.write((log+'\n').encode('utf-8'))
        print(log)

    def get_ncores(self):
        hw_thr_cnts_map = {
            Runner.CORE_FINE_GRAIN:cpupol.test_hw_thr_cnts_fine_grain,
            Runner.CORE_COARSE_GRAIN:cpupol.test_hw_thr_cnts_coarse_grain,
        }
        ncores = []
        test_hw_thr_cnts = hw_thr_cnts_map.get(self.CORE_GRAIN,
                                               cpupol.test_hw_thr_cnts_fine_grain)
        for n in test_hw_thr_cnts:
            if n > self.npcpu:
                break
            ncores.append(n)
        return ncores

    def exec_cmd(self, cmd, out=None):
        # TODO: Include here something that we call perf record

        p = subprocess.Popen(cmd, shell=True, stdout=out, stderr=out)
        p.wait()
        return p

    def keep_sudo(self):
        self.exec_cmd("sudo -v", self.dev_null)

    def drop_caches(self):
        cmd = ' '.join(["sudo",
                        os.path.normpath(
                            os.path.join(CUR_DIR, "drop-caches"))])
        self.exec_cmd(cmd, self.dev_null)

    def set_cpus(self, ncore):
        if self.active_ncore == ncore:
            return
        self.active_ncore = ncore
        if ncore is 0:
            ncores = "all"
        else:
            ncores = ','.join(map(lambda c: str(c), cpupol.seq_cores[0:ncore]))
        cmd = ' '.join(["sudo",
                        os.path.normpath(
                            os.path.join(CUR_DIR, "set-cpus")),
                        ncores])
        self.exec_cmd(cmd, self.dev_null)

    def add_bg_worker_if_needed(self, bench, ncore):
        if bench.endswith(self.BENCH_BG_SFX):
            ncore = min(ncore + 1, self.nhwthr)
            return (ncore, 1)
        return (ncore, 0)

    # INFO: Let's settle the lock_stat flag here
    def set_lock_stat(self):
        self.exec_cmd("sudo sh -c \"echo 0 > /proc/lock_stat\"", self.dev_null);
        self.exec_cmd("sudo sh -c \"echo 1 > /proc/sys/kernel/lock_stat\"", self.dev_null)

    # INFO: Let's unset the lock_stat flag here
    def unset_lock_stat(self, path_string):
        self.exec_cmd("sudo sh -c \"echo 0 > /proc/sys/kernel/lock_stat\"", self.dev_null)
        self.exec_cmd("sudo sh -c \"cp /proc/lock_stat ./logs/"+path_string+"\"", self.dev_null)
        print(path_string)
        print(path_string)
        print(path_string)
        print(path_string)
        print(path_string)
        print(path_string)
        #self.exec_cmd("mv lock_stat ./logs/"+path_string, self.dev_null)

    def prepre_work(self, ncore):
        self.keep_sudo()
        self.exec_cmd("sudo sh -c \"echo 0 >/proc/sys/kernel/lock_stat\"",
                      self.dev_null)
        self.drop_caches()
        self.exec_cmd("sync", self.dev_null)
        self.set_cpus(ncore)

    def pre_work(self):
        self.keep_sudo()
        self.drop_caches()
        # INFO: included
        self.set_lock_stat()

        if RUN_OPROFILE:
            self.oprofile = subprocess.Popen(["operf", "--system-wide"])


    def post_work(self, media, bench, idx_core, fs):
        self.keep_sudo()
        # INFO: included
        self.unset_lock_stat("lock_stat_"+media+"_"+bench+"_"+str(idx_core)+"_"+fs)
        if RUN_OPROFILE:
            self.oprofile.send_signal(signal.SIGINT)
            stoud, stderr = self.oprofile.communicate()

            # INFO: we are doing here what has been done in the ZSS/exp/run_fx file
            self.exec_cmd("mkdir ./logs/oprofile_"+str(idx_core)+"_"+bench+"_"+media+"_"+fs, self.dev_null);
            self.exec_cmd("mv oprofile_data ./logs/oprofile_"+str(idx_core)+"_"+bench+"_"+media+"_"+fs, self.dev_null);

        if RUN_PERF:
            folder_prefix = "perf_"+media+"_"+bench+"_"+fs+"_"+str(idx_core)

            self.exec_cmd("mkdir "+folder_prefix, self.dev_null)
            self.exec_cmd("mv perf.data "+folder_prefix, self.dev_null)
            self.exec_cmd("mv "+folder_prefix+" logs", self.dev_null)


    def unset_loopdev(self):
        self.exec_cmd(' '.join(["sudo", "losetup", "-d", Runner.LOOPDEV]),
                      self.dev_null)

    def umount(self, where):
        while True:
            p = self.exec_cmd("sudo umount " + where, self.dev_null)
            if p.returncode is not 0:
                break
        (umount_hook, self.umount_hook) = (self.umount_hook, [])
        map(lambda hook: hook(), umount_hook);

    def init_mem_disk(self):
        self.unset_loopdev()
        self.umount(self.tmp_path)
        self.unset_loopdev()
        self.exec_cmd("mkdir -p " + self.tmp_path, self.dev_null)
        if not self.mount_tmpfs("mem", "tmpfs", self.tmp_path):
            return False;
        self.exec_cmd("dd if=/dev/zero of="
                      + self.disk_path +  " bs=1G count=1024000",
                      self.dev_null)
        p = self.exec_cmd(' '.join(["sudo", "losetup",
                                    Runner.LOOPDEV, self.disk_path]),
                          self.dev_null)
        if p.returncode == 0:
            self.umount_hook.append(self.deinit_mem_disk)
        return (p.returncode == 0, Runner.LOOPDEV)

    def deinit_mem_disk(self):
        self.unset_loopdev()
        self.umount(self.tmp_path)

    def init_nvme_disk(self):
        return (os.path.exists(Runner.NVMEDEV), Runner.NVMEDEV)

    def init_ssd_disk(self):
        return (os.path.exists(Runner.SSDDEV), Runner.SSDDEV)

    def init_hdd_disk(self):
        return (os.path.exists(Runner.HDDDEV), Runner.HDDDEV)

    def init_media(self, media):
        _init_media = self.HOWTO_INIT_MEDIA.get(media, None)
        if not _init_media:
            return (False, None)
        (rc, dev_path) = _init_media()
        return (rc, dev_path)

    def mount_tmpfs(self, media, fs, mnt_path):
        p = self.exec_cmd("sudo mount -t tmpfs -o mode=0777,size="
                          + self.DISK_SIZE + " none " + mnt_path,
                          self.dev_null)
        return p.returncode == 0

    def mount_anyfs(self, media, fs, mnt_path):
        (rc, dev_path) = self.init_media(media)
        if not rc:
            return False

        p = self.exec_cmd("sudo mkfs." + fs
                          + " " + self.HOWTO_MKFS.get(fs, "")
                          + " " + dev_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd(' '.join(["sudo mount -t", fs,
                                    dev_path, mnt_path]),
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo chmod 777 " + mnt_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        return True

    def mount_ext4_no_jnl(self, media, fs, mnt_path):
        (rc, dev_path) = self.init_media(media)
        if not rc:
            return False

        p = self.exec_cmd("sudo mkfs.ext4"
                          + " " + self.HOWTO_MKFS.get(fs, "")
                          + " " + dev_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo tune2fs -O ^has_journal %s" % dev_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd(' '.join(["sudo mount -t ext4",
                                    dev_path, mnt_path]),
                          self.dev_null)
        if p.returncode is not 0:
            return False
        p = self.exec_cmd("sudo chmod 777 " + mnt_path,
                          self.dev_null)
        if p.returncode is not 0:
            return False
        return True

    def mount(self, media, fs, mnt_path):
        mount_fn = self.HOWTO_MOUNT.get(fs, None)
        if not mount_fn:
            return False;

        self.umount(mnt_path)
        self.exec_cmd("mkdir -p " + mnt_path, self.dev_null)
        return mount_fn(media, fs, mnt_path)

    def _match_config(self, key1, key2):
        for (k1, k2) in zip(key1, key2):
            if k1 == "*" or k2 == "*":
                continue
            if k1 != k2:
                return False
        return True

    def gen_config(self):
        for ncore in sorted(self.ncores, reverse=True):
            for bench in self.BENCH_TYPES:
                for media in self.MEDIA_TYPES:
                    for dio in self.DIRECTIOS:
                        for fs in self.FS_TYPES:
                            if fs == "tmpfs" and media != "mem":
                                continue
                            mount_fn = self.HOWTO_MOUNT.get(fs, None)
                            if not mount_fn:
                                continue
                            if self._match_config(self.FILTER, \
                                                  (media, fs, bench, str(ncore), dio)):
                                yield(media, fs, bench, ncore, dio)

    def fxmark_env(self):
        env = ' '.join(["PERFMON_LEVEL=%s" % self.PERFMON_LEVEL,
                        "PERFMON_LDIR=%s"  % self.log_dir,
                        "PERFMON_LFILE=%s" % self.perfmon_log])
        return env

    def get_bin_type(self, bench):
        if bench.startswith("filebench_"):
            return (self.filebench_path, bench[len("filebench_"):])
        if bench.startswith("dbench_"):
            return (self.dbench_path, bench[len("dbench_"):])
        return (self.fxmark_path, bench)

    def fxmark(self, media, fs, bench, ncore, nfg, nbg, dio):
        self.perfmon_log = os.path.normpath(
            os.path.join(self.log_dir,
                         '.'.join([media, fs, bench, str(nfg), "pm"])))
        (bin, type) = self.get_bin_type(bench)
        directio = '1' if dio is "directio" else '0'

        if directio is '1':
            if fs is "tmpfs":
                print("# INFO: DirectIO under tmpfs disabled by default")
                directio='0';
            else:
                print("# INFO: DirectIO Enabled")

        # INFO: Created a lambda function to define when the perf should be called

        call_perf = lambda : "perf record -g -e 'ext4:*' --call-graph dwarf -- " if RUN_PERF else " "
        # XXX
        # call_perf = lambda : "perf record -g --call-graph dwarf -- " if RUN_PERF else " "
        cmd = ' '.join([self.fxmark_env(),
                        call_perf(),
                        bin,
                        "--type", type,
                        "--ncore", str(ncore),
                        "--nbg",  str(nbg),
                        "--duration", str(self.DURATION),
                        "--directio", directio,
                        "--root", self.test_root,
                        "--profbegin", "\"%s\"" % self.perfmon_start,
                        "--profend",   "\"%s\"" % self.perfmon_stop,
                        "--proflog", self.perfmon_log])
        p = self.exec_cmd(cmd, self.redirect)
        if self.redirect:
            for l in p.stdout.readlines():
                self.log(l.decode("utf-8").strip())

    def fxmark_cleanup(self):
        cmd = ' '.join([self.fxmark_env(),
                        "%s; rm -f %s/*.pm" % (self.perfmon_stop, self.log_dir)])
        self.exec_cmd(cmd)
        # XXX: We are commenting here because we created specialized methods to do this
        #self.exec_cmd("sudo sh -c \"echo 0 >/proc/sys/kernel/lock_stat\"",
         #             self.dev_null)

    def run(self):
        try:
            cnt = -1
            self.log_start()
            for (cnt, (media, fs, bench, ncore, dio)) in enumerate(self.gen_config()):
                (ncore, nbg) = self.add_bg_worker_if_needed(bench, ncore)
                nfg = ncore - nbg

                if self.DRYRUN:
                    self.log("## %s:%s:%s:%s:%s" % (media, fs, bench, nfg, dio))
                    continue

                self.prepre_work(ncore)
                if not self.mount(media, fs, self.test_root):
                    self.log("# Fail to mount %s on %s." % (fs, media))
                    continue
                self.log("## %s:%s:%s:%s:%s" % (media, fs, bench, nfg, dio))
                self.pre_work()

                ###########################################
                # INFO: Here is where things happen indeed #
                ###########################################

                self.fxmark(media, fs, bench, ncore, nfg, nbg, dio)
                self.post_work(media, bench, ncore, fs)
            self.log("### NUM_TEST_CONF  = %d" % (cnt + 1))
        finally:
            signal.signal(signal.SIGINT, catch_ctrl_C)
            self.log_end()
            self.fxmark_cleanup()
            self.umount(self.test_root)
            self.set_cpus(0)

def confirm_media_path():
    print("%" * 80)
    print("%% WARNING! WARNING! WARNING! WARNING! WARNING!")
    print("%" * 80)

    # FIXME FIXME FIXME FIXME
    # FIXME: Removed this user input part to avoid blocking
    # yn = input("All data in %s, %s, %s and %s will be deleted. Is it ok? [Y,N]: "
    #         % (Runner.HDDDEV, Runner.SSDDEV, Runner.NVMEDEV, Runner.LOOPDEV))
    # if yn != "Y":
    #     print("Please, check Runner.LOOPDEV and Runner.NVMEDEV")
    #     exit(1)
    # yn = input("Are you sure? [Y,N]: ")
    # if yn != "Y":
    #     print("Please, check Runner.LOOPDEV and Runner.NVMEDEV")
    #     exit(1)
    # FIXME FIXME FIXME FIXME

    print("%" * 80)
    print("\n\n")

if __name__ == "__main__":
    # config parameters
    # -----------------
    #
    # o testing core granularity
    # - Runner.CORE_FINE_GRAIN
    # - Runner.CORE_COARSE_GRAIN
    #
    # o profiling level
    # - PerfMon.LEVEL_LOW
    # - PerfMon.LEVEL_PERF_RECORD
    # - PerfMon.LEVEL_PERF_PROBE_SLEEP_LOCK
    # - PerfMon.LEVEL_PERF_PROBE_SLEEP_LOCK_D  # do NOT use if you don't understand what it is
    # - PerfMon.LEVEL_PERF_LOCK                # do NOT use if you don't understand what it is
    # - PerfMon.LEVEL_PERF_STAT                # for cycles and instructions
    #
    # o testcase filter
    # - (storage device, filesystem, test case, # core, directio | bufferedio)

    # XXX: Here is where we get input from commands arguments

    NUM_CORES_CFG_ARG = "4"
    MEDIA_TYPE_CFG_ARG = "nvme"
    BENCH_TYPE_CFG_ARG = "DBRH"
    IO_TYPE_CFG_ARG = "bufferedio"
    RAMDISK_PATH_CFG_ARG = "/mnt/ramdisk1"
    RUN_PERF = 0
    RUN_OPROFILE = 0

    # If there is arguments, lets use them
    if (len(sys.argv) > 3):
        # Received values
        NUM_CORES_CFG_ARG = sys.argv[1]
        MEDIA_TYPE_CFG_ARG = sys.argv[2]
        BENCH_TYPE_CFG_ARG = sys.argv[3]
        IO_TYPE_CFG_ARG = sys.argv[4]
        RAMDISK_PATH_CFG_ARG = sys.argv[5]
        RUN_PERF = int(sys.argv[6])
        RUN_OPROFILE = int(sys.argv[7])

    run_config = [
        (Runner.CORE_FINE_GRAIN,
         PerfMon.LEVEL_LOW,
         (str(MEDIA_TYPE_CFG_ARG), "*", str(BENCH_TYPE_CFG_ARG), str(NUM_CORES_CFG_ARG), str(IO_TYPE_CFG_ARG))),
        # ("mem", "*", "DWOL", "80", "directio")),
        # ("mem", "tmpfs", "filebench_varmail", "32", "directio")),
        # (Runner.CORE_COARSE_GRAIN,
        #  PerfMon.LEVEL_PERF_RECORD,
        #  ("*", "*", "*", "*", "bufferedio")),
        #
        # (Runner.CORE_COARSE_GRAIN,
        #  PerfMon.LEVEL_PERF_RECORD,
        #  ("*", "*", "*", str(cpupol.PHYSICAL_CHIPS * cpupol.CORE_PER_CHIP), "*"))
    ]

    confirm_media_path()
    for c in run_config:
        runner = Runner(c[0], c[1], c[2])
        runner.run()
