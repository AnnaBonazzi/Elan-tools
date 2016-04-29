import os
import time
import argparse
import calendar
import xml.etree.ElementTree as et
from datetime import datetime
from xml.dom import minidom

# Template configuration

# Primary tags to look for
primaryTags = ['GES_03']

# tier_id -> (linguistic_type_ref, parent)
tierConfig = {
	'Speaker':('Person', None),
	'Speech':('Speech', 'Speaker'),
	'Rectangle':('Coordinates','Speaker'),
	'Gesture':('Gesture','Speaker'),
	'Circle':('Coordinates','Gesture'),
	'Head':('Head','Gesture'),
	'Body':('Body','Gesture'),
	'Arms & hands':('Arms & hands','Gesture')
}

# linguistic_type_id -> (constraints, graphic_references, time_alignable)
linguisticTypeConfig = {
	'Person':(None, 'false', 'true'),
	'Speech':('Included_In', 'false', 'true'),
	'Coordinates':('Included_In', 'false', 'true'),
	'Gesture':('Included_In', 'false', 'true'),
	'Head':('Included_In', 'false', 'true'),
	'Body':('Included_In', 'false', 'true'),
	'Arms & hands':('Included_In', 'false', 'true')
}

# seg file attribute -> corresponding tier id
segTierConfig = {
	'Speaker':'Speaker',
	'BoundingBox':'Rectangle',
	'Speech':'Speech',
	'Gesture':'Gesture',
	'BoundingCircle':'Circle',
	'Head':'Head',
	'Body':'Body',
	'Arms & Hands':'Arms & hands'
}

# Annotation class representing 1 ELAN annotation
class Annotation:
	tierID = None
	text = None
	start_time = None # in ms
	end_time = None # in ms
	
	def toString(self):
		return 'tierID: '+str(self.tierID)+', start_time: '+str(self.start_time)+', end_time: '+str(self.end_time)+', text='+str(self.text.replace('\n', ''))

# Read the output file
def readEafFile(filename):
	tree = et.parse(filename)
	
	# get ANNOTATION_DOCUMENT
	annDoc = tree.getroot()
	assert annDoc.tag == 'ANNOTATION_DOCUMENT', 'Error in parsing eaf file: The root element is not ANNOTATION_DOCUMENT'
	
	# get TIME_ORDER
	timeOrder = annDoc.find('TIME_ORDER')
	assert timeOrder != None, 'Error in parsing eaf file: Could not find TIME_ORDER element'
	if timeOrder==None:
		print 'Could not find TIME_ORDER'
		exit()
	
	# get max TIME_SLOT_ID
	timeSlotMaxID = -1
	for timeSlot in timeOrder.iter('TIME_SLOT'):
		timeSlotID = int(timeSlot.get('TIME_SLOT_ID')[2:])
		timeSlotMaxID = max(timeSlotMaxID, timeSlotID)
		
	# get max ANNOTATION_ID
	annMaxID = -1
	for alignableAnn in annDoc.iterfind('TIER/ANNOTATION/ALIGNABLE_ANNOTATION'):
		annID = int(alignableAnn.get('ANNOTATION_ID')[1:])
		annMaxID = max(annMaxID, annID)
	
	# get tiers	
	tiers = {}
	for tier in annDoc.iter('TIER'):
		tiers[tier.get('TIER_ID')] = tier
	
	return (timeSlotMaxID+1, annMaxID+1, annDoc, timeOrder, tiers)

# Write output in eaf format
def createEmptyEafStructure(videoFilename):
	# Get timestamp and timezone difference
	tm = calendar.timegm(time.gmtime())
	utc_offset = datetime.fromtimestamp(tm) - datetime.utcfromtimestamp(tm)
	sign='+'
	if utc_offset.days<0:
		sign='-'
		utc_offset = datetime.utcfromtimestamp(tm) - datetime.fromtimestamp(tm)
	offset_hours = int(round((utc_offset.seconds/3600)))
	
	# Create the basic elements of the eaf file
	annDoc = et.Element('ANNOTATION_DOCUMENT', {
		'AUTHOR':'',
		'DATE': datetime.now().strftime("%Y-%m-%dT%H:%M:%S")+sign+str(offset_hours)+':00',
		'FORMAT':'2.8', 
		'VERSION':'2.8',
		'xmlns:xsi':'http://www.w3.org/2001/XMLSchema-instance',
		'xsi:noNamespaceSchemaLocation':'http://www.mpi.nl/tools/elan/EAFv2.8.xsd'
		})
	header = et.SubElement(annDoc, 'HEADER', {
		'MEDIA_FILE':'',
		'TIME_UNITS':'milliseconds'
		})
	mediaDesc = et.SubElement(header, 'MEDIA_DESCRIPTOR', {
		'MEDIA_URL':'file://'+os.path.abspath(videoFilename),
		'MIME_TYPE':'video/mp4',
		})
	timeOrder = et.SubElement(annDoc, 'TIME_ORDER')
	
	# Create tier structure
	tiers = {}
	for tierID in tierConfig.keys():
		(ling_type, parent) = tierConfig[tierID]
		tier = et.SubElement(annDoc, 'TIER')
		tier.set('TIER_ID', tierID)
		tier.set('LINGUISTIC_TYPE_REF', ling_type)
		if (parent != None):
			tier.set('PARENT_REF', parent)
		tiers[tierID] = tier
		
	# Create linguistic type structure
	lingTypes = {}
	for lingTypeID in linguisticTypeConfig.keys():
		(constraints, graphic_references, time_alignable) = linguisticTypeConfig[lingTypeID]
		lingType = et.SubElement(annDoc, 'LINGUISTIC_TYPE')
		lingType.set('LINGUISTIC_TYPE_ID', lingTypeID)
		if constraints != None:
			lingType.set('CONSTRAINTS', constraints)
		if graphic_references != None:
			lingType.set('GRAPHIC_REFERENCES', graphic_references)
		if time_alignable != None:
			lingType.set('TIME_ALIGNABLE', time_alignable)
		lingTypes[lingTypeID] = lingType
	
	# Create default constraints
	constraints = [
		['Time subdivision of parent annotation\'s time interval, no time gaps allowed within this interval','Time_Subdivision'],
		['Symbolic subdivision of a parent annotation. Annotations refering to the same parent are ordered','Symbolic_Subdivision'],
		['1-1 association with a parent annotation','Symbolic_Association'],
		['Time alignable annotations within the parent annotation\'s time interval, gaps are allowed','Included_In']]
	for (desc, ster) in constraints:
		et.SubElement(annDoc, 'CONSTRAINT', {
			'DESCRIPTION':desc,
			'STEREOTYPE':ster
			})
	return (0, 0, annDoc, timeOrder, tiers)
	
# Read seg file and produce a list of Annotation objects
def segToAnnList(filename):
	annList = []
	videoStartTime = os.path.basename(filename)[:15]
	videoStartTime = calendar.timegm(time.strptime(videoStartTime, "%Y-%m-%d_%H%M"))
	with open(filename, 'r') as fp:
		for line in fp:
			if len(line.split('|'))>3 and any(primaryTag in line.split('|')[2] for primaryTag in primaryTags):
				# Get start time
				startTime = line.split('|')[0]
				startTime, startTimeMs = startTime.split('.')
				startTime = calendar.timegm(time.strptime(startTime, "%Y%m%d%H%M%S"))
				startTime = (startTime-videoStartTime)*1000+int(startTimeMs)
				# Get end time
				endTime = line.split('|')[1]
				endTime, endTimeMs = endTime.split('.')
				endTime = calendar.timegm(time.strptime(endTime, "%Y%m%d%H%M%S"))
				endTime = (endTime-videoStartTime)*1000+int(endTimeMs)
				# Get tiers and annotations
				segAnns = line.split('|')[3:]
				for segAnn in segAnns:
					segTier,text = segAnn.split('=')
					tier = segTierConfig[segTier]
					ann = Annotation()
					ann.start_time = startTime
					ann.end_time = endTime
					ann.tierID = tier
					ann.text = text.replace('\n', '')
					annList.append(ann)
	return annList

# Convert seg to eaf
def segToEaf(segFilename, eafFilename, template, overwrite):	
	# Extract data from the seg file
	annList = segToAnnList(segFilename)
	print 'Found the following annotations:'
	for ann in annList:
		print ann.toString()
	print ''
	# Build a basic eaf file
	if (template != None and not os.path.isfile(template)):
		print 'Could not find the template file ' + str(template)
		print 'Creating an empty file instead'
		template = None
	if (template != None):
		timeSlotMaxID, annMaxID, annDoc, timeOrder, tiers = readEafFile(template)
	else:
		videoFilename = os.path.basename(segFilename)[:-4] + '.mp4'
		timeSlotMaxID, annMaxID, annDoc, timeOrder, tiers = createEmptyEafStructure(videoFilename)
	# Put annotations into the eaf file
	for ann in annList:
		annID = 'a'+str(annMaxID)
		annMaxID += 1
		id1 = 'ts'+str(timeSlotMaxID)
		id2 = 'ts'+str(timeSlotMaxID+1)
		timeSlotMaxID += 2
		time1 = ann.start_time
		time2 = ann.end_time
		et.SubElement(timeOrder, 'TIME_SLOT', {
			'TIME_SLOT_ID':id1,
			'TIME_VALUE':str(time1)
			})
		et.SubElement(timeOrder, 'TIME_SLOT', {
			'TIME_SLOT_ID':id2,
			'TIME_VALUE':str(time2)
			})
		annEaf = et.SubElement(tiers[ann.tierID], 'ANNOTATION')
		align_ann = et.SubElement(annEaf, 'ALIGNABLE_ANNOTATION', {
			'ANNOTATION_ID':annID,
			'TIME_SLOT_REF1':id1,
			'TIME_SLOT_REF2':id2
			})
		annValue = et.SubElement(align_ann, 'ANNOTATION_VALUE')	
		annValue.text = ann.text
		
	# Make the output more presentable
	resultString = et.tostring(annDoc, 'utf-8')
	reparsed = minidom.parseString(resultString)
	resultString = reparsed.toprettyxml(indent="	")
	# Remove empty lines (not sure where they come from when using templates)
	newResultString = ''
	for line in resultString.split('\n'):
		if not line.isspace():
			newResultString += line+'\n'
	resultString = newResultString
	# Write output to file
	if (os.path.isfile(eafFilename) and not overwrite):
		print 'Output file already exists and -overwrite is not specified. Cannot write output.'
		exit()
	with open(eafFilename, 'w') as out:
		out.write(resultString)
				
if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='seg to eaf file converter.\nIt currently supports the http://vrnewsscape.ucla.edu/dropbox/Redhen-04-single.etf template.')
	parser.add_argument('input', help='input .seg file')
	parser.add_argument('output', help='output .eaf file')
	parser.add_argument('-template', help='use this file as the base structure instead of creating output from scratch (.eaf format required)')
	parser.add_argument('-overwrite', action='store_true', help='delete the existing output file and create a new one instead')
	args = parser.parse_args()
	input = args.input
	output = args.output
	overwrite = args.overwrite
	template = args.template
	segToEaf(input, output, template, overwrite)
