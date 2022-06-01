import numpy as np

def sigmoid_function(x):
    return 1 / (1 + np.exp(-x))


def sigmoid_derivative(x):
    return x * (1 - x)


class NeuralNet:

    def __init__(self):
        np.random.seed(1)

        self.synaptic_weights = np.random.random((3, 1)) - 1

    def think(self, input):
        input2 = np.float_(input)
        output = sigmoid_function(np.dot(input2, self.synaptic_weights))
        return output

    def train(self, training_input, training_output, training_iterations):
        for iteration in range(training_iterations):
            output = self.think(training_input)

            # calc error
            error = training_output - output

            # calc weight adjustments uisng sigmoid derivative
            adjustments = np.dot(training_input.T, error * sigmoid_derivative(output))

            # adjust synaptic weights
            self.synaptic_weights += adjustments


if __name__ == "__main__":
    neural_network = NeuralNet()

    training_inputs = np.array([[0, 0, 1], [1, 1, 1], [1, 0, 1], [0, 1, 1]])

    training_outputs = np.array([[0, 1, 1, 0]]).T

    np.random.seed(1)

    print("Random synaptic starting weights: \n", neural_network.synaptic_weights)

    neural_network.train(training_inputs, training_outputs, 100)

    print("Synaptic weights after training: \n", neural_network.synaptic_weights)

    # User inputs

    A = str(input("Input 1: "))
    B = str(input("Input 2: "))
    C = str(input("Input 3: "))

    print("User input situation: ", A, B, C)

    print("Output Data: \n", neural_network.think([A, B, C]))
