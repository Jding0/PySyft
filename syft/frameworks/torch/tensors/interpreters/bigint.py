import syft
import torch as th
import numpy as np
from syft.generic.tensor import AbstractTensor

from syft.generic.frameworks.hook.hook_args import (
    register_type_rule,
    register_forward_func,
    register_backward_func,
    one,
)

class BigIntTensor(AbstractTensor):
    def __init__(
        self,
        owner=None,
        id=None,
        enc_prec:int=2**63 - 1,
        max_val:int=2**128,
        tags: set = None,
        description: str = None,
    ):
        """Initializes a Fixed Precision tensor, which encodes all decimal point
        values using an underlying integer value.

        The FixedPrecision enables to manipulate floats over an interface which
        supports only integers, Such as _SPDZTensor.

        This is done by specifying a precision p and given a float x,
        multiply it with 10**p before rounding to an integer (hence you keep
        p decimals)

        Args:
            owner: An optional BaseWorker object to specify the worker on which
                the tensor is located.
            id: An optional string or integer id of the FixedPrecisionTensor.
        """
        super().__init__(tags=tags, description=description)

        self.owner = owner
        self.id = id if id else syft.ID_PROVIDER.pop()
        self.child = None

        self.n_shares = 0
        while enc_prec ** self.n_shares < max_val:
            self.n_shares += 1

        self.enc_prec = enc_prec
        self.max_val = max_val

    def encode_val(self, x):
        shares = list()

        for share_i in (range(self.n_shares)):
            share = (x % (self.enc_prec ** (share_i + 1))) // (self.enc_prec ** share_i)
            shares.append(share)

        return th.tensor(shares)

    def encode(self, x):
        shares = list()

        # encode as numpy to ensure we don't accidentally overflow
        if(isinstance(x, th.Tensor)):
            x = x.numpy()

        for val in x.flatten():
            shares.append(self.encode_val(val))

        shares = th.cat(shares).view(x.shape + th.Size([self.n_shares]))
        self.child = shares
        return self

    def decode(self, shares):
        val = 0
        for share_i, share in enumerate(shares):
            val += (self.enc_prec ** share_i) * share
        return val

    def long(self):

        numpy_shares = self.child.view(-1, self.shape[-1]).numpy()
        values = list()
        for val_shares in list(numpy_shares):
            values.append(self.decode(val_shares))

        return th.LongTensor(np.array(values)).view(self.shape[0:-1])

### Register the tensor with hook_args.py ###
register_type_rule({BigIntTensor: one})
register_forward_func({BigIntTensor: lambda i: BigIntTensor._forward_func(i)})
register_backward_func(
    {BigIntTensor: lambda i, **kwargs: BigIntTensor._backward_func(i, **kwargs)}
)