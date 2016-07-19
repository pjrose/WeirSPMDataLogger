#!/usr/bin/env bash

tempdir = /home/pi/temp/
homedir = /home/pi

function cleanup{
  sudo mount -o remount,ro /
  rm -rf /home/pi/temp/
}
trap cleanup EXIT

sudo mount -o remount,rw /
mkdir -p $tempdir 
cd $tempdir
rm -rf $tempdir 
git clone https://github.com/pjrose/WeirSPMDataLogger.git
sudo rsync -a tempdir homedir

