#!/usr/bin/python
#
# Master in /mnt/tvnews3/sergiy_turchyn/eaf_to_seg/
#
# Written by Sergiy Turchyn <sxt313@case.edu>, 2016-02-29
#
# To do: Extend support to a more complex template
#
# Changelog:
#
#       2016-03-02 Add help screen, dynamic script name
#
# --------------------------------------------------------------------------------------------------

# Libraries
import os
import poioapi.annotationgraph
import time
import shutil
import re
import calendar
import sys
from datetime import datetime

maxAnnDifference = 0 # How close do annotations have to be to be considered the same?

sourceProgram = os.path.basename(sys.argv[0])

# Define what information we want for each annotation 
# Represents all data about a single time window
class Annotation:
	text = {} # tier->text pairs
	startTime = -1
	endTime = -1
	primaryTag = ''
		
	# Converts annotation to seg string format
	# Also returns the start time as float (to find the proper location to paste the annotation)
	# If annotation needs to be split in several lines depending on attributes, toSegString() should return all of them joined by '\n'
	def toSegString(self, videoStartTime):
		# Get the timestamps and primary tag
		annStartTime = videoStartTime + self.startTime/1000
		annStartTime_ms = divmod(self.startTime,1000)[1]
		annStartTimeFloat = annStartTime + float(annStartTime_ms)/1000
		annEndTime = videoStartTime + self.endTime/1000
		annEndTime_ms = divmod(self.endTime,1000)[1]
		segStringBase = ''
		segStringBase += time.strftime("%Y%m%d%H%M%S", time.gmtime(annStartTime))
		segStringBase += '.' + str(annStartTime_ms).zfill(3) + '|'
		segStringBase += time.strftime("%Y%m%d%H%M%S", time.gmtime(annEndTime))
		segStringBase += '.' + str(annEndTime_ms).zfill(3) + '|'
		segStringBase += self.primaryTag
		
		# Form 3 possible lines depending on annotation tiers present
		# Have to define tier by tier to preserve order and rename some tiers
		segString1 = '' # Speaker, Bounding Box, Speech
		segString2 = '' # Gesture, Bounding Circle, Head, Body, Arms & Hands
		segString3 = '' # Any remaining attributes (if present)
		
		# Define segString1 
		tier = 'Speaker'
		if tier in self.text.keys():
			segString1 += '|' + tier + '=' + self.text[tier]
		tier = 'Rectangle'
		if tier in self.text.keys():
			segString1 += '|BoundingBox=' + self.text[tier]
		tier = 'Speech'
		if tier in self.text.keys():
			segString1 += '|' + tier + '=' + self.text[tier]
			
		# Define segString2
		tier = 'Gesture'
		if tier in self.text.keys():
			segString2 += '|' + tier + '=' + self.text[tier]
		tier = 'Circle'
		if tier in self.text.keys():
			segString2 += '|BoundingCircle=' + self.text[tier]
		tier = 'Head'
		if tier in self.text.keys():
			segString2 += '|' + tier + '=' + self.text[tier]
		tier = 'Body'
		if tier in self.text.keys():
			segString2 += '|' + tier + '=' + self.text[tier]
		tier = 'Arms & hands'
		if tier in self.text.keys():
			segString2 += '|Arms & Hands=' + self.text[tier]
			
		# Define segString3
		for tier in self.text.keys():
			annText = self.text[tier]
			if tier not in ['Speaker', 'Rectangle', 'Speech', 'Gesture', 'Circle', 'Head', 'Body', 'Arms & hands'] and annText!='':
				segString3 += '|' + tier + '=' + annText
		
		segString = '\n'.join([segStringBase + t for t in [segString1, segString2, segString3] if t!='']) + '\n'
		return segString, annStartTimeFloat
	
# Creates the credit line
def getCreditBlockLine(inputFilename, primaryTag, sourceProgram):
	result = ''
	author = ''
	with open(inputFilename, 'r') as fp:
		for line in fp:
			match = re.search('(<ANNOTATION_DOCUMENT.*?AUTHOR=")([^"]*)(")', line)
			if match:
				author = match.group(2)
				break
	currTime = time.strftime("%Y-%m-%d %H:%M", time.gmtime())
	result = primaryTag + '|' + currTime + '|Source_Program=' + sourceProgram + '|Source_Person=' + author + '\n'
	#'GES_03|2016-02-09 23:10|Source_Program=eaf2seg-01.py|Source_Person=Elizabeth Zima|Codebook='
	return result
			
# Converts .eaf file to graf-python format
def eafToGraf(inputFilename):
	ag = poioapi.annotationgraph.AnnotationGraph.from_elan(inputFilename)
	return ag.graf
	
# Takes graf object and produces a list of Annotation elements
def grafToList(grafObject, primaryTag):
	annotationList = []
	print 'Number of annotation elements: ' + str(len(grafObject.nodes.items()))
	for (nodeID, node) in grafObject.nodes.items(): 		
 		# Gets the annotation text
 		numFeatures = len(node.annotations.get_first().features)
 		annText = ''
 		if numFeatures>0:
 			annText = node.annotations.get_first().features.get_value('annotation_value')
 			
 		# Convert nodeID to regionID
 		# Assumes that region ID is node ID where 'naXX' is replaced with 'raXX'
 		head,sep,tail = nodeID.rpartition('na')
 		regionID = head + 'ra' + tail
 		region = grafObject.regions[regionID]
 		
 		# Get the tier name
 		tier = nodeID.split('..')[1]
 		
 		# Get the start and end times
 		startTime, endTime = region.anchors
 		
 		# Check if an annotation object exists with the same start and end times
 		alreadyExists = False
 		for ann in annotationList:
 			if abs(ann.startTime-startTime)<=maxAnnDifference and abs(ann.endTime-endTime)<=maxAnnDifference:
 				ann.text[tier] = annText
 				alreadyExists = True
 		if not alreadyExists:
			# Create an annotation object
			ann = Annotation()
			ann.text = {}
			ann.text[tier] = annText
			ann.startTime = startTime
			ann.endTime = endTime
			ann.primaryTag = primaryTag
			annotationList.append(ann)
 	return annotationList
 	
# Takes an annotation list and add to the seg file
def listToSeg(annList, inputFilename, outputFilename, clipOffset, creditBlockLine):
	# Read the video start time
	videoStartTime = os.path.basename(outputFilename)[:15]
	videoStartTime = calendar.timegm(time.strptime(videoStartTime, "%Y-%m-%d_%H%M"))
	videoStartTime += clipOffset
	# sort annotations according to the start time
	annList = sorted(annList, key=lambda ann:ann.startTime)
	# Write the annotations one by one
	tempOutputFilename = outputFilename+'.tmp'
	with open(outputFilename, 'r') as originalSeg:
		with open(tempOutputFilename, 'w') as newSeg:
			creditLineWritten = False
			i = 0
			annString, annStartTimeFloat = annList[i].toSegString(videoStartTime)
			for line in originalSeg:
				if (len(line.split('|')[0])==18):
					# Line contains annotation
					# Write the credit block line before annotations start
					if (not creditLineWritten):
						newSeg.write(creditBlockLine)
						creditLineWritten = True			
					# Compare the start times and write annotations if startTime is lower than in the seg file
					lineStartTime = line.split('|')[0]
					lineStartTimeFloat = calendar.timegm(time.strptime(lineStartTime.split('.')[0], "%Y%m%d%H%M%S")) + float(lineStartTime.split('.')[1].ljust(3,'0'))/1000
					while(annStartTimeFloat < lineStartTimeFloat and i < len(annList)):
						# Write all annotations that should be here
						newSeg.write(annString)
						#print str(annStartTimeFloat) + ' < ' + str(lineStartTimeFloat)
						#print annString
						#print line
						i += 1
						if (i < len(annList)):
							annString, annStartTimeFloat = annList[i].toSegString(videoStartTime)
				elif (line.startswith('END|')):
					# Write the credit block if not written yet
					if (not creditLineWritten):
						newSeg.write(creditBlockLine)
						creditLineWritten = True
					# Write all the remaining annotations at the end
					while(i < len(annList)):
						# Write all annotations that should be there
						annString, annStartTimeFloat = annList[i].toSegString(videoStartTime)
						newSeg.write(annString)
						i += 1

				newSeg.write(line)
	
	# Write to the output seg file
	shutil.move(tempOutputFilename, outputFilename)
	
# Convert eaf to seg using the above functions
# useSweep=False means that the seg file will already be located at the outputFilename location 
# 		 and does not have to be copied from the sweep location
def eafToSeg(inputFilename, outputFilename, primaryTag='GES_03', sourceProgram=sourceProgram, useSweep=True):
	inputFilename = os.path.abspath(inputFilename)
	outputFilename = os.path.abspath(outputFilename)
	# Check input and output files
	if (not os.path.isfile(inputFilename)):
		print 'The input file does not exist: ' + str(inputFilename)
		return
	if (os.path.isfile(outputFilename)):
		print 'The output file already exists and will be overwritten: ' + str(outputFilename)
	if ((not useSweep ) and (not os.path.isfile(outputFilename))):
		print 'The output file does not exist (using sweep location is turned off): ' + str(outputFilename)
		return
	if (not os.path.exists(os.path.dirname(outputFilename))):
   		os.makedirs(os.path.dirname(outputFilename))
   		print 'Created directory ' + str(os.path.dirname(outputFilename))
	
	# Copy the seg file from sweep folder to segDirectory
	if useSweep:
		videoStartTime = os.path.basename(outputFilename)[:15]
		segFileLocation = os.path.join('/sweep/', videoStartTime[0:4], videoStartTime[0:7], videoStartTime[0:10], os.path.basename(outputFilename))
		if (not os.path.isfile):
			print 'Could not find the .seg file in ' + str(segFileLocation)
			return
		shutil.copy2(segFileLocation, os.path.dirname(outputFilename))
	
	# Calculate clip offset from the filename
	clipOffset = 0.0
	match = re.search('(_)(\d+)(-\d+.eaf)', inputFilename)
	if match:
		clipOffset = float(match.group(2))
	print 'Clip offset is ' + str(clipOffset) + ' seconds.'
	
	# Convert eaf to seg
	grafObject = eafToGraf(inputFilename)
	creditBlockLine = getCreditBlockLine(inputFilename, primaryTag, sourceProgram)
	annotationList = grafToList(grafObject, primaryTag)
	listToSeg(annotationList, inputFilename, outputFilename, clipOffset, creditBlockLine)
				
# Help screen
if __name__ == '__main__':
	if (len(sys.argv)-1!=2) or ( sys.argv[1] == "-h" ):
		print "".join([ "\n","\t","This script converts Elan .eaf annotations to NewsScape .seg files." ])
		print "".join([ "\n","\t","It currently supports the https://github.com/RedHenLab/Elan-tools/blob/master/Redhen-04-single.etf template." ])
		print "".join([ "\n","\t","Usage:","\n" ])
		print "".join([ "\t","\t",sourceProgram," input.eaf output.seg" ])
		print "".join([ "\n","\t","Example:","\n" ])
		print "".join([ "\t","\t",sourceProgram," 2007-03-07_1900_US_KTTV-FOX_Montel_Williams_Show_797-1277.eaf 2007-03-07_1900_US_KTTV-FOX_Montel_Williams_Show.seg" ])
		print "".join([ "\n","\t","The script reads NewsScape's output.seg file from the sweep directory." ])
		print "".join([ "\t","It overwrites the output file in the current directory if it exists.","\n" ])
		sys.exit()
	inputFilename = sys.argv[1]
	outputFilename = sys.argv[2]
	eafToSeg(inputFilename, outputFilename, useSweep=True)
