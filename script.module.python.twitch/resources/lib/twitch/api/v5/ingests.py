# -*- encoding: utf-8 -*-
# https://dev.twitch.tv/docs/v5/reference/ingests/

from ...queries import V5Query as Qry
from ...queries import query


# required scope: none
@query
def ingests():
    q = Qry('ingests', use_token=False)
    return q