import yaml

from receipts.common.settings import repo_root


class NoDuplicateKeysLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        repeated = sorted({k for k in keys if keys.count(k) > 1})
        assert not repeated, f'config.yaml repeats {repeated}'
        return super().construct_mapping(node, deep=deep)


def test_config_names_each_key_once():
    with open(repo_root() / 'config.yaml') as f:
        yaml.load(f, Loader=NoDuplicateKeysLoader)
