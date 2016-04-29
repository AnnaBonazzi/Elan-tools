# eaf_to_seg
This script converts Elan .eaf annotations to NewsScape .seg files.

It currently supports the https://github.com/RedHenLab/Elan-tools/blob/master/Redhen-04-single.etf template.

Usage:

	eaf2seg-01.py input.eaf output.seg

Example:

	eaf2seg-01.py 2007-03-07_1900_US_KTTV-FOX_Montel_Williams_Show_797-1277.eaf 2007-03-07_1900_US_KTTV-FOX_Montel_Williams_Show.seg

The script reads NewsScape's output.seg file from the sweep directory.
It overwrites the output file in the current directory if it exists.

Please contribute by improving the template. Just ensure that your changes are reflected in the eaf2seg conversion script.

If you want to make major changes, please fork the template and the script. That way you create a new template-filter pair.
