to compile for testing

python -m compileall -f "<this_dir>"
	will compile into __pycache__ inside each folder
	.pyc file names must match no ".cpython-39"
or
python -m -b compileall -f "<this_dir>"
	(the -b flag will not write python version in each files name, but will same files next to .py files)

then replace inside "\Stardew Valley\Mods\Speak\lib\speech-client\dist\lib"
(Speak might be called StardewSpeak)
replace all .pyc inside "game_menu" and "menus" folders
then paste remaining .pyc files (modified) into the library.zip (inside the mod's lib dir)

also note main.py gets compiled into the exe so, needs recompiling after modifying
also may be slower to load