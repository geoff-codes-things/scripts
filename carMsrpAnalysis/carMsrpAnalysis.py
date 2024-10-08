# This script conducts analysis on MSRP data for USA car pricing
# data sourced from https://www.kaggle.com/datasets/CooperUnion/cardataset
# Written by Geoff Kottmeier

import sys
import traceback
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
import os
from time import gmtime, strftime
from datetime import datetime

# ============= ARGUMENTS =============
parser = argparse.ArgumentParser()
parser.add_argument('--exploratory','-e', help='Runs the exploratory analyis, generating plots and summary info about data.', action="store_true", required=False, default=False)
parser.add_argument('--model','-m', help='Generate and test a model.', action="store_true", required=False, default=False)
parser.add_argument('--predict','-p', help='Prompt the user for input to generate a prediction.', action="store_true", required=False, default=False)
parser.add_argument('--verbose','-v', help='For debugging', action="store_true", required=False, default=False)

# ============= FILE INTERACTION =============
def loadCsv():
	filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)),"car-features-msrp.csv")
	df = pd.read_csv(filepath)

	# Make sure thevalues are of expected types
	df['MSRP'] = df['MSRP'].astype(int)
	if not isinstance(df['Market Category'], list):
		df['Market Category'] = df['Market Category'].str.split(',')
	df['Engine Fuel Type'] = df['Engine Fuel Type'].astype(str)

	return df

# ============= EXPLORATION =============
def exploreCarData(df):
	verboseprint("Commencing exploring!")

	print("\n\nData set head:")
	print(df.head())

	print("\n\nCount of entries for each automaker:")
	print(df['Make'].value_counts())

	print("\n\nSummary statistics for each column of data:")
	print(df.describe().apply(lambda x: x.apply('{0:.5f}'.format)))

	print("\n\nSummary statistics for MSRP, MPG, and Horsepower by Make:")
	for make in df['Make'].unique():

		print("========  " + make + "  ========")
		for column in ['MSRP','highway MPG','Engine HP']:
			print("*** " + column + " ***")
			print(df[df['Make'] == make][column].describe())
			print()

	verboseprint("Exploring complete...")

def visualizeCarData(df):
	verboseprint("Commencing visualizations!")

	sns.set(rc = {'figure.figsize':(20,5)})

	sns.boxplot(x='MSRP', data=df)
	sns.stripplot(x='MSRP', data=df, jitter=True)
	plt.xlabel("MSRP ($, millions)")
	plt.title("Box Plot of All MSRPs in Data Set")
	plt.show()

	plot = sns.violinplot(x='Make', y='MSRP', data=df)
	plot.set_xticklabels(plot.get_xticklabels(), rotation=90)
	plt.ylabel("MSRP ($, millions)")
	plt.title("Violin Plot of MSRP by Make")
	plt.show()

	plot = sns.violinplot(x='Engine Fuel Type', y='MSRP', data=df)
	plot.set_xticklabels(plot.get_xticklabels(), rotation=90)
	plt.ylabel("MSRP ($, millions)")
	plt.show()

	sns.lmplot(x='Engine HP', y='MSRP', data=df, fit_reg=True,line_kws={'color': 'red'})
	plt.ylabel("MSRP ($, millions)")
	plt.title("MSRP by Engine HP")
	plt.show()

	df.plot(y='MSRP', x='highway MPG', kind='scatter')
	plt.ylabel("MSRP ($, millions)")
	plt.title("MSRP by highway MPG")
	plt.show()

	sns.violinplot(y='MSRP', x='Engine Cylinders', data=df)
	plt.ylabel("MSRP ($, millions)")
	plt.title("MSRP by Engine Cylinders")
	plt.show()

	ax = df.groupby(df['Year'])["MSRP"].mean().plot(kind="line",rot=25)
	ax = df.groupby(df['Year'])["MSRP"].median().plot(kind="line",rot=25)
	plt.xlabel("Year")
	plt.ylabel("Average MSRP ($)")
	plt.legend(["Mean", "Median"])
	plt.title("Average and Median MSRP by Year")
	plt.show()

	sns.histplot(df['MSRP' ],bins=100)
	plt.xlabel("Averarge MSRP ($, millions)")
	plt.ylabel("Count")
	plt.title("Distribution of MSRP")
	plt.show()

	verboseprint("Visualizations complete!")
	return True

# ============= MODELLING =============
def preprocessCarData(df):
	# add an index column
	df.insert(0, 'index', value=range(len(df)))

	# Encode string values in data
	le = LabelEncoder()
	df['Transmission Type'] = le.fit_transform(df['Transmission Type'])
	df['Driven_Wheels'] = le.fit_transform(df['Driven_Wheels'])
	df['Vehicle Size'] = le.fit_transform(df['Vehicle Size'])
	df['Vehicle Style'] = le.fit_transform(df['Vehicle Style'])
	df['Engine Fuel Type'] = le.fit_transform(df['Engine Fuel Type'])
	df['Make'] = le.fit_transform(df['Make'])

	# Create a new DataFrame with boolean columns for each market category
	df = pd.get_dummies(df.join(pd.Series(df['Market Category'].apply(pd.Series).stack().reset_index(1, drop=True),name='Category1')).drop('Market Category', axis=1).rename(columns={'Category1': 'Market Category'}),columns=['Market Category']).groupby('index', as_index=False).sum()

	# Assume vehicles with no door count have 4 doors
	df['Number of Doors'] = df['Number of Doors'].fillna(4)

	return df

def createMsrpModel(df):
	x = df.drop(['MSRP','Model','Engine Fuel Type','Engine HP','Engine Cylinders','Engine Fuel Type'], axis=1)
	y = df['MSRP']

	x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)

	rdg = Ridge(alpha = 0.5)
	rdg.fit(x_train, y_train)
	y_pred = rdg.predict(x_test)

	print(rdg.get_params(deep=False))
	print("Model Score: " + str(rdg.score(x_test, y_test)))
	mse = mean_squared_error(y_test, y_pred)
	r2 = r2_score(y_test, y_pred)
	print("Mean Squared Error:", mse)
	print("Out of Sample R-squared:", r2)


	sns.histplot(y_test,bins=30)
	sns.histplot(y_pred,bins=30)
	plt.xlabel("MSRP ($, millions)")
	plt.ylabel("Count")
	plt.title("Predicted MSRPs vs Actual MSRP for Out of Sample Test Data")
	plt.show()


	return rdg, x_test, y_test



# ============= EXECUTION =============
def verbosePrintSetup(verbosestate):
	if verbosestate:
		def verboseprintfunc(*args):
			timestamp = datetime.now()
			timestampstr = timestamp.strftime("%d-%m-%Y, %H:%M:%S")
			for arg in args:
				print(timestampstr + ' - verbose: ' + str(arg))
	else:
		verboseprintfunc = lambda *a: None
	return verboseprintfunc



def run():
	global verboseprint

	# Establish arguments and verbose print if user passed -v
	args = parser.parse_args()
	verboseprint = verbosePrintSetup(args.verbose)

	df = loadCsv()

	# Runs the exporatory analysis, generating some charts and summary information about the raw data
	if args.exploratory:
		exploreCarData(df)
		visualizeCarData(df)

	if args.model:
		df = preprocessCarData(df)
		msrpmodel, x_test, y_test = createMsrpModel(df)

	if args.predict:
		# TODO
		print("Thanks for trying to predict!")
		print("This hasn't been written yet...")


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


if __name__ == '__main__':
    main()