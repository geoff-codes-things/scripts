# textReplacer
#
# This script is intended to:
#    - Replace a batch of strings in a text file
#    - Reverse the replacement of strings
# It can also:
#    - Warn the user if strings were encountered that closely match a string intended for replacement
#    - Save the result to a user defined or default file path
#
# Written by Geoff Kottmeier, 2025

import argparse
import csv
import re
import datetime
import os
from datetime import datetime
import sys
import traceback

# ============= ARGUMENTS =============
parser = argparse.ArgumentParser(description="Replace strings in a text file.")
parser.add_argument("-t","--text", help="Path to the input text file.", required=True)
parser.add_argument("-c","--csv", help="Path to the CSV file containing replacement mappings. It should be two columns with the headings 'beforeReplacement' and 'afterReplacement'.\nNote: default is to match complete strings (e.g. replacing 'ant' with 'bug' would NOT replace the first part of 'anthill' or change 'ants' to 'bugs'. Adding a *, like 'ant*' would change all cases of the string, thus making it 'bughill' and 'bugs'. If you want this to be reversible, both columns should have a * at the end of the string.)", required=True)
parser.add_argument("-o","--output", help="(Optional) Path to the output text file. If not passed, new file will be saved to /tmp/ with a timestamp.", required=False)
parser.add_argument("-v", "--verbose", action="store_true", help="(Optional) Enables verbose output to provide additional logging in the console.", required=False)
parser.add_argument("-r", "--reverse", action="store_true", help="(Optional) Inverts the 'before' and 'after' columns to run the replacement in revers order.", required=False)
parser.add_argument("-w", "--close_match_warning", action="store_true", help="Enables close match warning mode. If a string closely matches one being replaced, displays a warning in the console with the close match and its context.", required=False)

# ============= FILE INTERACTION =============

# Reads a text file in.
# If file can't be found, bails the script with an error
def readTextFile(textFile):
    verboseprint(f'Attempting to read {textFile}')
    try:
        with open(textFile, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        sys.exit(f"Text file '{textFile}' not found.")

# Reads a csv file in.
# If file can't be found or doesn't match expected format, bails the script with an error
# Expected format is a two column csv with headers 'beforeReplacement' and 'afterReplacement'
def readCsvFile(csvFile, reverse):
    verboseprint(f'Attempting to read {csvFile}')
    replacements = {}
    try:
        with open(csvFile, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if reverse:
                    replacements[row['afterReplacement']] = row['beforeReplacement']
                else:
                    replacements[row['beforeReplacement']] = row['afterReplacement']
        return replacements
    except FileNotFoundError:
        sys.exit(f"CSV file '{csvFile}' not found.")
    except KeyError:
        sys.exit("CSV file must have 'beforeReplacement' and 'afterReplacement' columns.")

# Writes text to a file at a provided path
# Bails out of the script if an issue occurs attempting to do so
def writeOutputFile(outputFile, text):
    try:
        with open(outputFile, 'w', encoding='utf-8') as f:
            f.write(text)
        return True
    except Exception as e:
        sys.exit(f"Error writing to output file: {e}")

# ============= DATA PROCESSING =============

# Replaces a specific string
# Attempts to preserve case (i.e. 'lower', 'Capitalized', or 'ALLCAPS')
# If the case is mixed, just sticks with 
def replaceMatch(match, after, count):
    original = match.group(0)

    if original.isupper(): 
        # if original is all caps
        result = after.upper()
        verboseprint(f'Encountered ALL-CAPS case "{original}"", using "{result}"')
    elif original.islower(): 
        # if original is all lower
        result = after.lower()
        verboseprint(f'Encountered all-lower case "{original}"", using "{result}"')
    elif original and original[0].isupper() and (len(original) == 1 or original[1:].islower()):
        # if first letter is capitalized and it's only one character or the rest of the string is lower case 
        result = after.capitalize()
        verboseprint(f'Encountered Capitalized case "{original}"", using "{result}"')
    else:
        # For mixed case, respect the capitalization of the first letter from the text file.
        # The rest of the string will simply preserve capitilization from the csv.
        if original[0].isupper():
            result = after[0].upper() + after[1:] if len(after) > 1 else after[0].upper()
        else:
            result = after[0].lower() + after[1:] if len(after) > 1 else after[0].lower()
        verboseprint(f'Encountered mixed capitilization case "{original}", using "{result}" (preserving case of first letter)')

    if result != original:
        count[0] += 1
    return result

def replaceStrings(text, replacements, reverse, close_match_warning):
    verboseprint("Starting string replacement...")

    # A very basic check to see how much of a string matches one of the replacements.
    # Intent is to catch things like "enemy" and "enemies" which the user may have intended, but not captured
    if close_match_warning:
        warned_matches = set()
        for before in replacements.keys():
            words = re.findall(r'\b\w+\b', text.lower())
            for word in words:
                if len(before) > 0 and len(word) > 0:
                    similarity = sum(1 for a, b in zip(before.lower(), word) if a == b) / max(len(before), len(word))
                    if similarity >= 0.7 and word != before.lower() and word not in warned_matches:
                        index = text.lower().find(word)
                        context = text[max(0, index - 30):min(len(text), index + 30)]
                        print(f"Warning: Close match found: '{word}' (similar to '{before}'). Context: '[...]{context}[...]'")
                        warned_matches.add(word)

    replacement_counts = {}

    # The actual finding and replacing logic...
    for before, after in replacements.items():
        verboseprint(f'Starting on replacing "{before}" with "{after}"')
        count = [0]

        if before.endswith("*"): # handling for when the user had the wildcard specifier '*' at the end of a string in the csv
            before_base = before[:-1]
            escaped_before_base = re.escape(before_base)
            text = re.sub(re.compile(escaped_before_base, re.IGNORECASE), lambda match: replaceMatch(match, after[:-1] if after.endswith("*") else after, count), text)
        else: # no wildcard
            escaped_before = re.escape(before)
            text = re.sub(re.compile(rf"\b{escaped_before}\b", re.IGNORECASE), lambda match: replaceMatch(match, after, count), text)

        replacement_counts[before] = count[0]

        if reverse:
            verboseprint(f"Replaced '{before}' with '{after}' (reverse), {count[0]} times.")
        else:
            verboseprint(f"Replaced '{before}' with '{after}', {count[0]} times.")

    return text

# ============= CONSOLE OUTPUT =============

# establishes either a functional print with timestamp if `verbosesate` is true,
# or does nothing with the passed information if false.
def verbosePrintSetup(verbosestate):
    if verbosestate:
        def verboseprintfunc(*args):
            timestamp = datetime.now()
            timestampstr = timestamp.strftime("%Y-%m-%d, %H:%M:%S")
            print(timestampstr + ' - verbose: ', end='')
            for arg in args:
                print(str(arg), end=' ')
            print()
    else:
        verboseprintfunc = lambda *a: None
    return verboseprintfunc


# ============= EXECUTION =============
def run():
    args = parser.parse_args()

    global verboseprint
    verboseprint = verbosePrintSetup(args.verbose)

    text = readTextFile(args.text)
    replacements = readCsvFile(args.csv, args.reverse)
    
    replacedText = replaceStrings(text, replacements, args.reverse, args.close_match_warning)

    if not args.output:
        timestampStr = datetime.now().strftime("%Y%m%d_%H%M%S")
        outputFile = os.path.join("/tmp", f"replaced_text_{timestampStr}.txt")
    else:
        outputFile = args.output

    if writeOutputFile(outputFile, replacedText):
        print(f"String replacement completed. Output saved to '{outputFile}'.")

def main():
    try:
        run()
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit('\nUser canceled... Stopping\n')
    except Exception as e:
        print('An unexpected error occurred: %s' % str(e), file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()