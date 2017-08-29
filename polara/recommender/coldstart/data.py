from collections import namedtuple
import numpy as np
import pandas as pd
from polara.recommender.data import RecommenderData


class ItemColdStartData(RecommenderData):
    def __init__(self, *args, **kwargs):
        super(ItemColdStartData, self).__init__(*args, **kwargs)

        self._test_sample = 1
        self._test_unseen_users = False

        # build unique items list to split them by folds
        itemid = self.fields.itemid
        self._unique_items = permute(self._data[itemid].unique())


    def _check_state_transition(self):
        new_state, update_rule = super(ItemColdStartData, self)._check_state_transition()
        if '_test_sample' in self._change_properties:
            update_rule['test_update'] = True
        return new_state, update_rule


    def _split_test_index(self):
        userid = self.fields.userid
        itemid = self.fields.itemid

        item_idx = np.arange(len(self._unique_items))
        cold_items_split = self._split_fold_index(item_idx, len(item_idx), self._test_fold, self._test_ratio)

        cold_items = self._unique_items[cold_items_split]
        cold_items_mask = self._data[itemid].isin(cold_items)
        return cold_items_mask


    def _split_data(self):
        assert self._test_ratio > 0
        assert not self._test_unseen_users
        update_rule = super(ItemColdStartData, self)._split_data()

        if any(update_rule.values()):
            testset = self._sample_test_items()
            self._test = self._test._replace(testset=testset)
        return update_rule


    def _sample_test_items(self):
        userid = self.fields.userid
        itemid = self.fields.itemid
        itemid_cold = '{}_cold'.format(itemid)
        test_split = self._test_split
        holdout = self.test.evalset
        user_has_cold_item = self._data[userid].isin(holdout[userid].unique())
        sampled = super(ItemColdStartData, self)._sample_testset(user_has_cold_item, holdout.index)
        testset = (pd.merge(holdout[[userid, itemid_cold]],
                            sampled[[userid, itemid]],
                            on=userid, how='inner')
                            .drop(userid, axis=1)
                            .drop_duplicates(subset=[itemid, itemid_cold])
                            .sort_values('{}_cold'.format(itemid)))
        return testset


    def _sample_holdout(self, test_split):
        itemid = self.fields.itemid
        itemid_cold = '{}_cold'.format(itemid)
        return (self._data.loc[test_split, list(self.fields)]
                    .rename(columns={itemid: itemid_cold}, copy=False))


    def _try_drop_unseen_test_items(self):
        # there will be no such items except cold-start items
        pass

    def _try_drop_invalid_test_users(self):
        # testset contains items only
        pass

    def _try_sort_test_data(self):
        # no need to sort by users
        pass

    def _assign_test_items_index(self):
        itemid = self.fields.itemid
        self._map_entity(itemid, self._test.testset)
        self._reindex_cold_items() # instead of trying to assign known items index

    def _assign_test_users_index(self):
        # skip testset as it doesn't contain users
        userid = self.fields.userid
        self._map_entity(userid, self._test.evalset)

    def _reindex_cold_items(self):
        itemid_cold = '{}_cold'.format(self.fields.itemid)
        cold_item_index = self.reindex(self.test.testset, itemid_cold, inplace=True, sort=False)
        try: # check if already modified item index to avoid nested assignemnt
            item_index = self.index.itemid.training
        except AttributeError:
            item_index = self.index.itemid
        new_item_index = (namedtuple('ItemIndex', 'training cold_start')
                                ._make([item_index, cold_item_index]))
        self.index = self.index._replace(itemid=new_item_index)
