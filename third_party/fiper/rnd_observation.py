"""FIPER RND_OE networks; see LICENSE and provenance.json.

Network factory bodies are copied verbatim from the pinned upstream RND_OE.
The standalone lifecycle removes Hydra/dataset/action dependencies. It is an
observation-only adaptation, not the combined FIPER failure predictor.
"""
import torch
from torch import nn


class ObservationRND(nn.Module):
    def __init__(self, input_dim, output_dim=128, *, initialize=True):
        super().__init__()
        self.obs_embedding_dim = input_dim
        self.output_size = output_dim
        self.target_network = self.get_target_network()
        self.predictor_network = self.get_predictor_network()
        if initialize:
            # Matches RNDBase.post_process for Linear layers.
            for layer in self.modules():
                if isinstance(layer, nn.Linear):
                    nn.init.orthogonal_(layer.weight, 2 ** .5)
                    if layer.bias is not None:
                        nn.init.zeros_(layer.bias)
        self.target_network.requires_grad_(False)

    def forward(self, input):
        # Upstream default rnd_loss=l2 uses nn.PairwiseDistance(p=2).
        target = self.target_network(input)
        prediction = self.predictor_network(input)
        return nn.functional.pairwise_distance(prediction, target, p=2)

    def get_target_network(self):
        # Define the target network architecture
        net = nn.Sequential(
            nn.Linear(in_features=self.obs_embedding_dim, out_features=1024),
            nn.LeakyReLU(),
            nn.Linear(in_features=1024, out_features=2048),
            nn.LeakyReLU(),
            nn.Linear(in_features=2048, out_features=4096),
            nn.LeakyReLU(),
            nn.Linear(in_features=4096, out_features=self.output_size),
        )
        return net

    def get_predictor_network(self):
        # Define the prediction network architecture
        net = nn.Sequential(
            nn.Linear(in_features=self.obs_embedding_dim, out_features=1024),
            nn.LeakyReLU(),
            nn.Linear(in_features=1024, out_features=2048),
            nn.LeakyReLU(),
            nn.Linear(in_features=2048, out_features=4096),
            nn.LeakyReLU(),
            nn.Linear(in_features=4096, out_features=2048),
            nn.ReLU(),
            nn.Linear(in_features=2048, out_features=1024),
            nn.ReLU(),
            nn.Linear(in_features=1024, out_features=self.output_size),
        )
        return net
