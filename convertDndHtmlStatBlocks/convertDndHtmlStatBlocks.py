import sys
import traceback
import os
import re
import argparse
import uuid
import time
import csv
import xml.etree.ElementTree as ET
from subprocess import Popen, PIPE

reload(sys)
sys.setdefaultencoding("utf-8")

# ============= PATTERNS =============
CREATURE_PATTERN = re.compile(r'(?P<name>.+?)\n(?P<metadata>.+?)\nArmor Class (?P<ac>.+)\nHit Points (?P<hp>.+)\nSpeed (?P<speed>.+)\n+STR\n(?P<strength>[0-9]+).+\n+DEX\n(?P<dexterity>[0-9]+).+\n+CON\n(?P<constitution>[0-9]+).+\n+INT\n(?P<intelligence>[0-9]+).+\n+WIS\n(?P<wisdom>[0-9]+).+\n+CHA\n(?P<charisma>[0-9]+).+\n+(Saving Throws (?P<savingthrows>.+)\n)?(Skills (?P<skills>.+)\n)?(Damage Vulnerabilities (?P<damagevulnerabilities>.+)\n)?(Damage Resistances (?P<damageresistances>.+)\n)?(Damage Immunities (?P<damageimmunities>.+)\n)?(Condition Immunities (?P<conditionimmunities>.+)\n)?(Senses (?P<senses>.+)\n)?(Languages (?P<languages>.+)\n)?(Challenge (?P<challenge>.+)\n)?(?P<attributes>[\S\s]+?)??Actions(.+)??\n(?P<actions>[\S\s]+?)(\nReactions\n(?P<reactions>[\S\s]+?))?(\nLegendary Actions\n(?P<legendaryactions>[\S\s]+?))?\n{2}', re.MULTILINE)
ITEM_PATTERN = re.compile(r'^(?P<itemtitle>.{0,45})\. (?P<itemdescription>[\S\s]+?(?=^.{0,45}\.|\Z))', re.MULTILINE)
METADATA_PATTERN = re.compile(r'(?P<size>Tiny|Small|Medium|Large|Huge|Gargantuan) (?P<type>.+), (?P<alignment>.+)$', re.MULTILINE)
CRUFT_PATTERN = re.compile(r'<.+?>', re.MULTILINE)
KEEP_PATTERN = re.compile(r'((.+)?\n){3}Armor Class[\S\s]+?([\s]+?\n){5}', re.MULTILINE)
RATING_PATTERN = re.compile(r'[0-9]+(\/[0-9]+)?(?= \()', re.MULTILINE)
PERCEPTION_PATTERN = re.compile(r'(?<=Perception )(\+|-)?[0-9]+', re.MULTILINE)
TEST_PATTERN = re.compile(r'\nArmor Class (?P<ac>.+)\n.+', re.MULTILINE)


# ============= ARGUMENTS =============
parser = argparse.ArgumentParser()
parser.add_argument('--files','-f', help='Files to process, string of paths separated by spaces. Spaces in path or file names should be escaped. eg "/tmp/Animals.txt,/tmp/Beasts\ large.txt,/tmp/Creatures.txt" Note: commas in the file names or paths will break things...', type=str, required=True)
parser.add_argument('--output','-o', help='Specify type of output - console, csv, xml, or txt. Note: XML is formatted for use as a compendium with Encounter Plus.', choices=["console","csv","xml","txt"], required=False, default='console')
parser.add_argument('--xmlinclude','-x', help='Path to an existing xml compendium for EncounterPlus, will keep anything in the existing compendium and add to it.', type=str, required=False)
parser.add_argument('--verbose','-v', help='For debugging', action="store_true", required=False, default=False)

# ============= PROCESSING =============

# preprocessHtml reads content from files and prepares them for processing
# Removes a bunch of unused stuff from the files for efficiency, and subs for special chars that break things that aren't html
# Returns one string with the processed content from the files
def preprocessHtml(files):
	results = "" # used to store results across multiple files
	
	files = files.replace("\ ","&nbsp;") #super hacky. should do this right with a regex.

	for file in files.split(" "):

		file = file.replace("&nbsp;", " ") # like i said... super hacky.

		verboseprint("processing " + str(file))
		processedfile = "" # used to store reuslts for one particular file at a time
		reader = open(file, "r")

		for line in reader:
			processedfile += str(line)

		# ditch all the <span>'s and <div>'s and html we don't care about 
		processedfile = re.sub(CRUFT_PATTERN, '', processedfile)

		# just keep the body of the page where the stack blocks live, not necessary but more efficient
		processedfile = re.search(KEEP_PATTERN, processedfile).group()

		# for some reason there's somtimes a line break and a non-breaking space. Get ridda that...
		processedfile = processedfile.replace("\n&nbsp;","")

		# a bunch of special html characters that will break the xml and csv output
		replacements = {"&minus;":"-", "&mdash;":"-", "&ndash;":"-", "&rsquo;":"'", "&nbsp;":" ", "&ldquo;":'"', "&rdquo;":'"', "&times;":'x', "&frac12;":'.5'}
		for badstr, goodstr in replacements.iteritems():
			verboseprint("Replacing " + badstr + " with " + goodstr)
			processedfile = processedfile.replace(badstr, goodstr)

		# done, add it to the complete results for all files
		results += processedfile

	verboseprint("Combined output after substitutions / removals: " + results)

	return results

# For lists that have headings (eg actions, reactions, etc)
# Breaks them up in separate items
def createItemList(originalstring):
	arrayOfItems = []
	matches = [m.groupdict() for m in ITEM_PATTERN.finditer(originalstring)]
	for match in matches:
		descriptionnoendlinebreak = match['itemdescription']
		if descriptionnoendlinebreak.endswith("\n"):
			descriptionnoendlinebreak = descriptionnoendlinebreak[:-1]
		arrayOfItems.append({'name':match['itemtitle'], 'text':descriptionnoendlinebreak})

	return arrayOfItems

# Takes a processed string based on the html file(s)
# Turns it into a array of dictionaries with the values from the stat blocks
def createDictFromData(incomingdata):
	verboseprint("Applying match pattern for creature stat blocks")
	verboseprint(str(CREATURE_PATTERN.pattern))
	matches = [m.groupdict() for m in CREATURE_PATTERN.finditer(incomingdata)]
	#matches = re.findall(TEST_PATTERN, incomingdata)
	verboseprint("Matches found:" + str(len(matches)))

	# create arrays of actions / attributes / etc 
	for match in matches:
		if match['attributes'] != None:
			match['attributesarray'] = createItemList(match['attributes'])
		if match['actions'] != None:
			match['actionsarray'] = createItemList(match['actions'])
		if match['reactions'] != None:
			match['reactionsarray'] = createItemList(match['reactions'])
		if match['legendaryactions'] != None:
			match['legendaryactionsarray'] = createItemList(match['legendaryactions'])

		if match['metadata'] != None:
			metadamatch = re.match(METADATA_PATTERN, match['metadata'])
			metadatadictraw = metadamatch.groupdict()
			metadatadict = {'size' : metadatadictraw['size'], 'sizeabbreviated' : metadatadictraw['size'][0].upper(), 'type' : metadatadictraw['type'], 'alignment' : metadatadictraw['alignment']}
			match['metadatadict'] = metadatadict

		# If it's listed, pull the passive perception value. If not, calculate one.
		if match['senses'] != None:
			if re.search(PERCEPTION_PATTERN, match['senses']):
				passiveperception = int(re.search(PERCEPTION_PATTERN, match['senses']).group())
			else:
				perceptionbonus = 0
				if match['skills'] != None:
					if re.search(PERCEPTION_PATTERN, match['skills']):
						perceptionbonus = int(re.search(PERCEPTION_PATTERN, match['skills']).group())	
				passiveperception = int((float(match['wisdom']) - 10.0)/2.0) + perceptionbonus
		match['passiveperception'] = passiveperception


	matches = sorted(matches, key=lambda k: k['name']) 
	return matches

# given a dictionary and a number of indents to put before each value
# turns it into a string in XML format
def dictToXML(data):
	indentation = ""
	xmlstr = ""
	if indent > 0:
		for x in range(0,indent):
			indentation += "\t"
	for key in sorted(data.keys()):
		xmlstr += indentation + "<" + key + ">" + str(data[key]) + "</" + key + ">\n"

	return xmlstr

def createXMLElementsFromDict(topelementname, subelementdict, basexml):
	newxml = basexml
	newsublement = ET.SubElement(newxml, topelementname)
	for key in sorted(subelementdict.keys()):
		newsubsublement = ET.SubElement(newsublement, str(key))
		newsubsublement.text = str(subelementdict[key])

	return newxml

# Changes the data structure to align with what Encounter Plus expects for each monster
# Turns the dict for each monster into an XML block for each monster
def makeMonsterforEncounterPlus(creature):
	#get a dict of just the values EncounterPlus cares about
	data_for_ep_monster = {}

	#start with the straight tanslatable...
	data_for_ep_monster = {'name':creature['name'],
		'size':creature['metadatadict']['sizeabbreviated'],
		'type':creature['metadatadict']['type'],
		'alignment':creature['metadatadict']['alignment'],
		'ac':creature['ac'],
		'hp':creature['hp'],
		'speed':creature['speed'],
		'str':creature['strength'],
		'dex':creature['dexterity'],
		'con':creature['constitution'],
		'int':creature['intelligence'],
		'wis':creature['wisdom'],
		'cha':creature['charisma'],
		'passive':creature['passiveperception']
		}

	# weird requirement for encounter plus; doesn't correlate to a value in stat blocks... so just calling them all enemies.
	data_for_ep_monster['role'] = "enemy"
	# another weird requirement for Encounter Plus; "slug" is just the name in lower case with hyphens instead of spaces.
	data_for_ep_monster['slug'] = creature['name'].lower().replace(" ", "-")
	# Encounter Plus wants the CR number only, no XP amount.
	if creature['challenge'] != None:
		data_for_ep_monster['cr'] = re.search(RATING_PATTERN, creature['challenge']).group()
	else:
		data_for_ep_monster['cr'] = 0
	
	# time to start creating some XML!
	xmlmonster = ET.Element('monster')

	# encounter plus wants a UUID for "id" of each monster
	xmlmonster.set('id', str(uuid.uuid4(	)))

	# add all the stuff that's simple to correlate from above
	for key in data_for_ep_monster.keys():
		newelement = ET.SubElement(xmlmonster, key)
		newelement.text = str(data_for_ep_monster[key])

	#deal with the fancier ones, that might be "none" or might be multiple values (eg actions, reactions, etc)
	if creature['attributes'] != None:
		for item in creature['attributesarray']:
			xmlmonster = createXMLElementsFromDict('trait',item,xmlmonster)
	if creature['actions'] != None:
		for item in creature['actionsarray']:
			xmlmonster = createXMLElementsFromDict('action',item,xmlmonster)
	if creature['reactions'] != None:
		for item in creature['reactionsarray']:
			xmlmonster = createXMLElementsFromDict('reaction',item,xmlmonster)
	if creature['legendaryactions'] != None:
		for item in creature['legendaryactionsarray']:
			xmlmonster = createXMLElementsFromDict('legendary',item,xmlmonster)


	return xmlmonster

def generateXMLforEncounterPlus(creatures, startingxml):
	verboseprint("converting " + str(len(creatures)) + " creatures to XML.")
	namesalreadyincompendium = []
	
	if startingxml:
		basexml = ET.parse(startingxml)
		compendiumxml = basexml.getroot()
		for monster in compendiumxml.iter('monster'):
			namesalreadyincompendium.append(monster.get('slug'))
	else:
		compendiumxml = ET.Element('compendium')
	for creature in creatures:
		if creature['name'] not in namesalreadyincompendium:
			verboseprint(creature['name'] + " added to compendium xml.")
			compendiumxml.append(makeMonsterforEncounterPlus(creature))
		else:
			verboseprint(creature['name'] + " already in compendium xml, appears to be duplicate, skipping.")

	return compendiumxml

def generateCSV(creatures):
	columns = ['name','size','type','alignment','ac','speed','strength','dexterity','constitution','intelligence','wisdom','charisma','savingthrows','skills','damagevulnerabilities','damageresistances','damageimmunities','conditionimmunities','senses','languages','challenge','attributes','actions','reactions','legendaryactions']

	outputcontent = [columns]

	for creature in creatures:
		row = []
		for column in columns:
			if column not in ['size','type','alignment']:
				row.append(creature[column])
			else:
				row.append(creature['metadatadict'][column])

		outputcontent.append(row)

	return outputcontent

def generateItemsText(heading,items):
	itemsstr = ""
	itemsstr += ("-- " + heading + " --\n")
	for item in items:
		itemsstr += ("* " + item['name'].upper() + ": " + item['text'] + "\n")

	itemsstr += "\n"

	return itemsstr


def generatePlainText(creatures):
	plainttextstr = ""

	plainttextstr += ("Here are your creatures!\n\n")

	for creature in creatures:
		plainttextstr += ("======== " + creature['name'].upper() + " ========\n")
		plainttextstr += ("Size: " + creature['metadatadict']['size'] + " || Type: " + creature['metadatadict']['type'] + " || Alignment: " + creature['metadatadict']['alignment'] + "\n")
		plainttextstr += ("STR " + creature['strength'] + " || DEX " + creature['dexterity'] + " || INT " + creature['intelligence'] + " || CON " + creature['constitution'] + " || CHA " + creature['charisma'] + "\n")
		plainttextstr += ("AC: " + creature['ac'] + " || HP: " + creature['hp'] + " || Speed: " + creature['speed'] + "\n")
		plainttextstr += ("\n")
		if creature['attributes'] != None:
			plainttextstr += generateItemsText("Attributes", creature['attributesarray'])
		if creature['actions'] != None:
			plainttextstr += generateItemsText("Actions", creature['actionsarray'])
		if creature['reactions'] != None:
			plainttextstr += generateItemsText("Reactions", creature['reactionsarray'])
		if creature['legendaryactions'] != None:
			plainttextstr += generateItemsText("Legendary Actions", creature['legendaryactionsarray'])

		plainttextstr += "\n"

	return plainttextstr


# ============= OUTPUT =============
def writeXMLToFile(outputcontent):
	timestamp = time.strftime("%Y%m%d-%H%M%S")
	newfileprefix = "/tmp/dndouput-" + timestamp 
	newfilepath = newfileprefix + ".xml"

	verboseprint("Creating XML file " + newfilepath)
	tree = ET.ElementTree(outputcontent)
	outputfile = open(newfilepath, "wb")
	tree.write(outputfile)
	outputfile.close()

	formattedfilepath = newfileprefix + "-formatted.xml"
	outputfile = open(formattedfilepath, "wb")
	verboseprint("Attempting to format")
	proc = Popen(['xmllint','--format',newfilepath], stdout=outputfile)
	proc.wait()

	outputfile.close()

	return formattedfilepath

def writeTextToFile(outputcontent, extension):
	timestamp = time.strftime("%Y%m%d-%H%M%S")
	newfilepath = "/tmp/dndouput-" + timestamp + "." + extension
	outputfile = open(newfilepath, "wb")
	outputfile.write(outputcontent)
	outputfile.close()
	return newfilepath

def writeCSVtoFile(outputcontent):
	timestamp = time.strftime("%Y%m%d-%H%M%S")
	newfilepath = "/tmp/dndouput-" + timestamp + ".csv"
	outputfile = open(newfilepath, "wb")
	writer = csv.writer(outputfile)
	writer.writerows(outputcontent)
	outputfile.close()

	return newfilepath

# ============= EXECUTION =============
def getverbosefunc(verboseenabled):
        if verboseenabled:
        	def verboseprintfunc(*args):
        		for arg in args:
           			print('VERBOSE: ' + arg)

           	return verboseprintfunc
        else:
        	return lambda *a: None 

def run():
	global verboseprint
	newfilepath = False

	args = parser.parse_args()

	verboseprint = getverbosefunc(args.verbose)

	dnddata = preprocessHtml(args.files)

	dnddata = createDictFromData(dnddata)

	if args.output == 'xml':
		outputcontent = generateXMLforEncounterPlus(dnddata, args.xmlinclude)
		newfilepath = writeXMLToFile(outputcontent)
	
	if args.output == 'console':
		outputcontent = generatePlainText(dnddata)
		print(outputcontent)

	if args.output == 'txt':
		outputcontent = generatePlainText(dnddata)
		newfilepath = writeTextToFile(outputcontent, "txt")

	if args.output == 'csv':
		outputcontent = generateCSV(dnddata)
		newfilepath = writeCSVtoFile(outputcontent)

	if newfilepath:
		print("Success! Your new file can be found at: " + newfilepath)

def main():
	try:
		run()
		sys.exit(0)
	except KeyboardInterrupt:
		sys.exit("\nUser cancelled, stopping...\n")
	except Exception as e:
		print >> sys.stderr, "An unexpected Error occurred: " + str(e)
		print >> sys.stderr, traceback.format_exc()
		sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
