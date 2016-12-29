from payu.forms import PayULiveUpdateForm
from silver.forms import GenericTransactionForm


class PayuTransactionForm(GenericTransactionForm, PayULiveUpdateForm):
    pass
