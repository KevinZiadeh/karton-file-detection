"""Karton File Detection Service."""

import json
import re
import subprocess
from typing import Any, ClassVar, cast

from karton.core import Karton, RemoteResource, Task
from magika import Magika

from .__version__ import __version__


class FileDetection(Karton):
    """
    Perform DiE, TrID, and Magika on samples, add tags and attributes.

    **Consumes:**
    ```
    {"type": "sample", "stage": "recognized"}
    ```

    **Produces:**
    ```
    {
        "headers": {"type": "sample", "stage": "analyzed"},
        "payload": {
            "sample": sample,
            "tags": <DiE tags>,
            "attributes": {
                "die": <Minimized DiE result>,
                "trid": <Minimized TrID result>,
                "magika": <Parsed Magika result>,
            }
        }
    }
    ```
    """

    identity = "karton.file-detection"
    filters: ClassVar = [
        {"type": "sample", "stage": "recognized"},
    ]
    version = __version__
    TRID_CUTOFF = 5

    @staticmethod
    def normalize(name: str) -> str:
        """
        Normalize the given string.

        Args:
            name (str): string to normalize

        Returns:
            str: normalized string

        """
        return name.lower().replace(": ", ":").replace(" ", "-")

    @staticmethod
    def get_tags_from_die(die_data: list[dict[str, Any]]) -> list[str]:
        """
        Parse output from DiE data and generate tags.

        Args:
            die_data (list[dict[str, Any]]): parsed DIE output

        Returns:
            list(str): list of tags to add to the sample

        """
        tags = set()
        for detected in die_data:
            if "values" not in detected:
                continue

            for packer in detected["values"]:
                if "type" in packer and "name" in packer:
                    packer_type = FileDetection.normalize(packer["type"])
                    packer_name = FileDetection.normalize(packer["name"])
                    if packer_type == "unknown" or packer_name == "unknown":
                        continue
                    if packer_type == "malware" and packer_name != "unknown":
                        tags.add(packer_name)
                    else:
                        tags.add(f"{packer_type}:{packer_name}")

        return list(tags)

    def extract_json_output_from_die(self, die_data: str, sample_hash: str) -> list[dict[str, Any]]:
        """
        Parse output from DiE string and extract JSON output.

        Args:
            die_data (str): raw DiE output
            sample_hash (str): hash of the sample

        Returns:
            list(str): list of tags to add to the sample

        """
        if not die_data:
            return []

        match = re.search(r"\{.*\}", die_data, re.DOTALL)

        if not match:
            self.log.error(
                    f"Could not find JSON object in DiE output for {sample_hash}",
                )
            return []

        json_str = match.group(0)
        parsed_data = json.loads(json_str)

        if "detects" not in parsed_data:
            self.log.error(
                f"{sample_hash} failed running file-detection. Error code 01",
            )
            return []

        output = []
        for detected in parsed_data["detects"]:
            if len(detected.get("values", [])) == 0:
                continue
            if len(detected.get("values", [])) == 1 and detected["values"][0]["type"] == "Unknown":
                continue
            output.append(detected)

        return output

    def extract_json_output_from_trid(self, trid_data: str, sample_hash: str) -> list[dict[str, Any]]:
        """
        Parse output from TrID string and extract JSON output.

        Args:
            trid_data (str): raw DiE output
            sample_hash (str): hash of the sample

        Returns:
            list(str): list of tags to add to the sample

        """
        if not trid_data:
            return []

        pattern = re.compile(r"(\d+(?:\.\d+)?)%\s+\((\.\w+)\)\s+(.+)")

        matches = pattern.findall(trid_data)

        if not matches:
            self.log.error(
                    f"Could not find JSON object in TrID output for {sample_hash}",
                )
            return []

        return [
                {
                    "percentage": float(percent),
                    "extension": ext,
                    "name": name.strip(),
                }
                for percent, ext, name in matches
                if float(percent) > self.TRID_CUTOFF
            ][::-1]

    def process(self, task: Task) -> None:
        """
        Entry point of this service.

        Takes a sample and perform DiE, TrID, and Magika on it. Pass all relevant data to next task.

        Args:
            task (Task): Karton task

        """
        sample_resource = cast("RemoteResource", task.get_resource("sample"))

        die_data = None
        with sample_resource.download_temporary_file() as f:
            die_data = subprocess.check_output(["/usr/bin/diec", "-j", "-d", "-u", "-g", "-a", f.name]).decode("utf-8")
            die_json = self.extract_json_output_from_die(die_data, sample_resource.sha256 or sample_resource.name)
            trid_data = subprocess.check_output(["/usr/local/bin/trid", f.name]).decode("utf-8")
            trid_json = self.extract_json_output_from_trid(trid_data, sample_resource.sha256 or sample_resource.name)
            magika_data = Magika().identify_path(f.name)
            magika_json = [{
                "label": magika_data.output.label.title(),
                "description": magika_data.output.description,
                "extensions": magika_data.output.extensions,
                "group": magika_data.output.group,
                "score": round(magika_data.score*100, 2),
            }]

        self.log.info(f"Successfully perform DiE, TrID, and Magika on {sample_resource.sha256}")

        if not die_json and not trid_json and not magika_json:
            return

        tags = FileDetection.get_tags_from_die(die_json)
        self.send_task(
            Task(
                headers={"type": "sample", "stage": "analyzed"},
                payload={
                    "sample": sample_resource,
                    "tags": tags,
                    "attributes": {
                        "die": die_json,
                        "trid": trid_json,
                        "magika": magika_json,
                    },
                },
            ),
        )
        self.log.info(f"Successfully pushed DiE, TrID, and Magika data for {sample_resource.sha256}")
