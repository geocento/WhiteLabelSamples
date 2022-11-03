This is a repository of adapter scripts for the orderer.

In WL you create an adapter and upload the adapter script to the service. This adapter can then be encapsulated in an orderer which can then be used in a policy. The script has to be written in Python 3.

This orderer is used when the system is asked to order the product, either in a fully automated way or from the operator requesting teh script to be ran.

When the orderer is triggered, it calls the following adapter script methods:
- create_order - called only once at the beginning, when the order is requested
- check_status - called on a polling mode to check the status of the order
- handle_callback (optional) - called on an asynchronous mode when a callback is made by the supplier API
- handle_download - called when the data is ready and needs downloading

These methods need to implemented in the script. The different examples available provide a blue print on how to implement them.
