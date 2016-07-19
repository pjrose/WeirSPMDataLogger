@echo on
for %%A in ("%~dp0\..") do set "root_parent=%%~fA"
"%~dp0winscp.com" /script="%~dp0winscp pi update script.txt" /parameter "%root_parent%"