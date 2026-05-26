There are a couple of problems with current sidebar navigation.
1. There are many elements on the sidebar such that when one scrolls to the bottom, and chooses a new session, they have to 
   scroll back to the top of the page in order to see the results for that session. 
2. The sidebar should be organized as follows:
    ```
    repo-owner/
        repo/
            commit1/
            commit2/
            ...
    ```
    For each commit, repo, and repo owner, we should keep track of:
    - Last modified time.
    - Number of edits.

    We will sort repo-owner by total number of edits.
    We will sort repos by last modified time.
    We will sort commits by last modified time.

    Each repo owner, repo, and commit will be annotated with last modified time and number of edits.


To support this change, I've added two fields to the SessionManifest:
```python
class SessionManifest(BaseModel):
    owner: str
    repo: str
    sha: str
    last_modified: datetime # added
    num_edits: int          # added
```