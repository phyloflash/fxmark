# LOG_FILE = logs_combined.log
# DISK_SIZE = 30G
# FS_TYPES = ext4_no_jnl
# DURATION = 30s
# CORE_PER_CHIP = 12
# BENCH_TYPES = DWOL,DWOM,DWAL,DWTL,DWSL,MWCL,MWCM,MWUL,MWUM,MWRL,MWRM,DRBL,DRBM,DRBH,MRPL,MRPM,MRPH,MRDL,MRDM
# CORE_SEQ = 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47
# SMT_LEVEL = 2
# MEDIA_TYPES = nvme
# PHYSICAL_CHIPS = 2
# DIRECTIO = bufferedio
# NCORES = 1,2,4,6,12,18,24
# MODEL_NAME = Intel(R) Xeon(R) CPU E5-2670 v3 @ 2.30GHz
# SYSTEM = Linux sierra 4.9.46 #1 SMP Thu Sep 21 23:46:31 KST 2017 x86_64 x86_64 x86_64 GNU/Linux

set term pdfcairo size 2.3in,2.3in font ',10'
set_out='set output "`if test -z $OUT; then echo sc.pdf; else echo $OUT; fi`"'
eval set_out
set multiplot layout 1,1

set title 'nvme:DWOM:bufferedio'
set xlabel '# cores'
set ylabel 'M ops/sec'
plot [0:][0:] 'nvme:ext4:DWOM:bufferedio.dat' using 1:2 title 'ext4' with lp ps 0.5, 'nvme:ext4_no_jnl:DWOM:bufferedio.dat' using 1:2 title 'ext4_no_jnl' with lp ps 0.5

unset multiplot
set output
