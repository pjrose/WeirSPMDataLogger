#!/usr/bin/env bash

tempdir=/home/pi/temp/
homedir=/home/pi/

function cleanup {
#   rm -rf $tempdir
   mount -o remount,ro /
}
trap cleanup EXIT

echo $tempdir
mount -o remount,rw /
rm -rf $tempdir
mkdir -p $tempdir 
cd $tempdir
git clone https://github.com/pjrose/WeirSPMDataLogger.git $tempdir
rsync -zvha $tempdir $homedir
