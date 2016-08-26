#!/usr/bin/env bash

#HOW TO USE:
#Copy the script.sh file to the pi home directory, then do the following.
#sudo chmod u+x ./githubsync.sh (Only needs to be done one time)

#to run it:
#sudo ./githubsync.sh 

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
rsync -zvha $tempdir $homedir --delete-after
chown $USER -R $homedir
chmod -R 755 $homedir



