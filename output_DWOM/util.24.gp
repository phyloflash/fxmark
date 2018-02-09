# LOG_FILE = logs_combined.log
# MEDIA_TYPES = nvme
# SYSTEM = Linux sierra 4.9.46 #1 SMP Thu Sep 21 23:46:31 KST 2017 x86_64 x86_64 x86_64 GNU/Linux
# SMT_LEVEL = 2
# CORE_SEQ = 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47
# DURATION = 30s
# CORE_PER_CHIP = 12
# PHYSICAL_CHIPS = 2
# FS_TYPES = ext4_no_jnl
# NCORES = 1,2,4,6,12,18,24
# DIRECTIO = bufferedio
# BENCH_TYPES = DWOL,DWOM,DWAL,DWTL,DWSL,MWCL,MWCM,MWUL,MWUM,MWRL,MWRM,DRBL,DRBM,DRBH,MRPL,MRPM,MRPH,MRDL,MRDM
# MODEL_NAME = Intel(R) Xeon(R) CPU E5-2670 v3 @ 2.30GHz
# DISK_SIZE = 30G

set term pdfcairo size 2.3in,2.3in font ',10'
set_out='set output "`if test -z $OUT; then echo util.24.pdf; else echo $OUT; fi`"'
eval set_out
set multiplot layout 1,1

set grid y
set style data histograms
set style histogram rowstacked
set boxwidth 0.5
set style fill solid 1.0 border -1
set ytics 10

set title 'nvme:DWOM:*:24:bufferedio'
set xlabel ''
set ylabel 'CPU utilization'
set yrange [0:100]
set xtics rotate by -45
set key out horiz
set key center top

# nvme:*:DWOM:24
plot '-' using 2:xtic(1) title 'user', '' using 3 title 'sys', '' using 4 title 'idle', '' using 5 title 'iowait'
  # ['user.util', 'sys.util', 'idle.util', 'iowait.util']
  "ext4" 0.132865 14.2705 83.2704 0.0470564
  "ext4_no_jnl" 0.147686 20.8982 76.7883 0.046067
e
  # ['user.util', 'sys.util', 'idle.util', 'iowait.util']
  "ext4" 0.132865 14.2705 83.2704 0.0470564
  "ext4_no_jnl" 0.147686 20.8982 76.7883 0.046067
e
  # ['user.util', 'sys.util', 'idle.util', 'iowait.util']
  "ext4" 0.132865 14.2705 83.2704 0.0470564
  "ext4_no_jnl" 0.147686 20.8982 76.7883 0.046067
e
  # ['user.util', 'sys.util', 'idle.util', 'iowait.util']
  "ext4" 0.132865 14.2705 83.2704 0.0470564
  "ext4_no_jnl" 0.147686 20.8982 76.7883 0.046067
e

unset multiplot
set output
