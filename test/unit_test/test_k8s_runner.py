import unittest

from je_web_runner.utils.k8s_runner import (
    K8sRunnerError,
    ShardJobConfig,
    render_job_manifests,
)
from je_web_runner.utils.k8s_runner.manifest import (
    render_job_yaml,
    render_yaml_documents,
)


class TestRenderJobManifests(unittest.TestCase):

    def test_creates_one_job_per_shard(self):
        config = ShardJobConfig(
            name_prefix="ci-run",
            image="ghcr.io/x/webrunner:latest",
            total_shards=3,
            actions_dir="/work/actions",
        )
        manifests = render_job_manifests(config)
        self.assertEqual(len(manifests), 3)
        names = [m["metadata"]["name"] for m in manifests]
        self.assertIn("ci-run-shard-1-of-3", names)
        self.assertIn("ci-run-shard-3-of-3", names)

    def test_args_carry_shard_and_actions_dir(self):
        manifests = render_job_manifests(ShardJobConfig(
            name_prefix="x",
            image="img",
            total_shards=2,
            actions_dir="/actions",
        ))
        first = manifests[0]
        container = first["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("--execute_dir", container["args"])
        self.assertIn("/actions", container["args"])
        self.assertIn("1/2", container["args"])

    def test_env_passes_through(self):
        config = ShardJobConfig(
            name_prefix="x", image="img", total_shards=1,
            actions_dir="/a", env={"FOO": "bar"},
        )
        first = render_job_manifests(config)[0]
        env_list = first["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertEqual(env_list, [{"name": "FOO", "value": "bar"}])

    def test_invalid_name_prefix_raises(self):
        with self.assertRaises(K8sRunnerError):
            render_job_manifests(ShardJobConfig(
                name_prefix="Bad_Prefix", image="img",
                total_shards=1, actions_dir="/a",
            ))

    def test_zero_shards_raises(self):
        with self.assertRaises(K8sRunnerError):
            render_job_manifests(ShardJobConfig(
                name_prefix="ok", image="img",
                total_shards=0, actions_dir="/a",
            ))


class TestYamlRendering(unittest.TestCase):

    def test_yaml_round_trip_contains_kind_job(self):
        text = render_job_yaml(ShardJobConfig(
            name_prefix="run", image="img", total_shards=2, actions_dir="/a",
        ))
        self.assertIn("kind: Job", text)
        self.assertIn("---", text)

    def test_render_yaml_documents_handles_empty(self):
        self.assertTrue(render_yaml_documents([]).strip() == "")


if __name__ == "__main__":
    unittest.main()
