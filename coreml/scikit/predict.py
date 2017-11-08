import coremltools

model =  coremltools.models.MLModel('houses.mlmodel')

# Make predictions
predictions = model.predict({'BDRMS': 1.0, 'BTRMS': 1.0, 'FMR': 1240})

print predictions
