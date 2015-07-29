#!/bin/sh
set -e

TOOL=$1
EXT=$2
TEST=$3

LOGFILE=$TEST.$TOOL.log
OUTFILE=$TEST.$TOOL.out
ERRFILE=$TEST.$TOOL.err

$TOOL ../ribosome.$EXT $TEST.$EXT.dna >$OUTFILE 2>$ERRFILE || 
    { env echo -en "[\033[91mERROR\033[0m ($ERRFILE)] "; exit; }

if diff $OUTFILE $TEST.check >$LOGFILE; then
	env echo -en "[\033[92mOK\033[0m] "
	rm $LOGFILE $OUTFILE $ERRFILE
else
	env echo -en "[\033[93mFAIL\033[0m ($LOGFILE)] "
fi
