@REM pip install pyinstaller==5.13

pyinstaller -D --hidden-import "PIL._imaging" ^
--add-data "fastshot/web/templates;fastshot/web/templates" ^
--add-data "fastshot/web/static;fastshot/web/static" ^
--add-data "fastshot/resources;fastshot/resources" ^
--add-data "fastshot/config.ini;fastshot" ^
--add-data "fastshot/_config_reset.ini;fastshot" ^
run.py