import pandas as pd


class ArticleFilterer:
    def __init__(self):
        pass

    def filter(self, dataframe: pd.DataFrame):
        dataframe = dataframe.copy()
        dataframe = dataframe.apply(self._get_mentions, axis=1)

        return dataframe[
            dataframe["company_mention"]
            & (
                dataframe["state_mention"]
                | dataframe["county_mention"]
                | dataframe["city_mention"]
            )
        ]

    def _get_mentions(self, row: pd.Series):
        return pd.Series(
            {
                "company_mention": self._has_company_mention(row),
                "state_mention": self._has_state_mention(row),
                "county_mention": self._has_county_mention(row),
                "city_mention": self._has_city_mention(row),
            }
        )

    @staticmethod
    def _has_company_mention(row: pd.Series):
        if str(row.get("company")).lower() in row.get("text", "").lower():
            return True

        return False

    @staticmethod
    def _has_state_mention(row: pd.Series):
        if str(row.get("state")).lower() in row.get("text", "").lower():
            return True

        return False

    @staticmethod
    def _has_county_mention(row: pd.Series):
        if str(row.get("county")).lower() in row.get("text", "").lower():
            return True

        return False

    @staticmethod
    def _has_city_mention(row: pd.Series):
        if str(row.get("city")).lower() in row.get("text", "").lower():
            return True

        return False
