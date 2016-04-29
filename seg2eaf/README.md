# seg_to_eaf
This script converts NewScape .seg annotations to Elan .eaf files.

It currently supports the https://github.com/RedHenLab/Elan-tools/blob/master/Redhen-04-single.etf template.

Usage:

	seg_to_eaf.py [-h] [-template TEMPLATE] [-overwrite] input output

	input - input .seg file
	output -  output .eaf file

	optional arguments:
		-h, --help          show help message and exit
		-template TEMPLATE - use this file as the base structure instead of creating output from scratch (.eaf format required)
		-overwrite - delete the existing output file and create a new one instead

Example:

	python seg_to_eaf.py 2007-03-07_1900_US_KTTV-FOX_Montel_Williams_Show.seg output_with_template.eaf -overwrite -template example_template.eaf
	python seg_to_eaf.py 2007-03-07_1900_US_KTTV-FOX_Montel_Williams_Show.seg output_without_template.eaf -overwrite 

Please contribute by improving the template. Just ensure that your changes are reflected in the seg_to_eaf conversion script.

If you want to make major changes, please fork the template and the script. That way you create a new template-filter pair.
