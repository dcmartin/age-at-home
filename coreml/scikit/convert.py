from sklearn.linear_model import LinearRegression
import pandas as pd

# Load data
#  1: METRO3
#  2: FMR
#  3: ROOMS
#  4: VALUE
#  5: BEDRMS
#  6: BDRMS
#  7: BTRMS
#  8: EXTRA
#  9: FMTMETRO3
data = pd.read_csv('houses.csv')

# Train a model
model = LinearRegression()
# BDRMS = bedrooms; BTRMS = bathrooms; FMR = Fair Market Rent; VALUE = assessor
model.fit(data[["BDRMS", "BTRMS", "FMR"]], data["VALUE"])

 # Convert and save the scikit-learn model
import coremltools
coreml_model = coremltools.converters.sklearn.convert(model, ["BDRMS", "BTRMS", "FMR"], "VALUE")
coreml_model.save("houses.mlmodel")
