import pathlib
from typing import Optional

from fastapi import APIRouter, Path, Depends, Response, status, Query, HTTPException
from git import Repo

from opal_server.policy.bundles.api import make_bundle
from opal_server.scopes.pull_engine import CeleryPullEngine
from opal_server.scopes.pullers import InvalidScopeSourceType, create_puller
from opal_server.scopes.scope_store import ScopeStore
from opal_common.git.bundle_maker import BundleMaker
from opal_server.config import opal_server_config
from opal_common.schemas.policy import PolicyBundle
from opal_server.scopes.scopes import ScopeConfig


def setup_scopes_api():
    router = APIRouter()
    scopes = ScopeStore(
        base_dir=opal_server_config.SCOPE_BASE_DIR,
        fetch_engine=CeleryPullEngine())

    def get_scopes():
        return scopes

    @router.get("/scopes/{scope_id}", response_model=ScopeConfig)
    async def get_scope(
        response: Response,
        scope_id: str = Path(..., title="Scope ID"),
        scopes: ScopeStore = Depends(get_scopes)
    ):
        try:
            return scopes.get_scope(scope_id)
        except KeyError:
            response.status_code = status.HTTP_404_NOT_FOUND

    @router.post("/scopes", status_code=status.HTTP_201_CREATED)
    async def add_scope(
        scope_config: ScopeConfig,
        scopes: ScopeStore = Depends(get_scopes)
    ):
        try:
            scope = scopes.add_scope(scope_config)
            return {
                "task_id": str(scope.task_id)
            }
        except InvalidScopeSourceType as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid scope source type: {e.invalid_type}'
            )

    @router.delete("/scopes/{scope_id}")
    async def delete_scope(
        response: Response,
        scope_id: str = Path(..., title="Scope ID to be deleted"),
        scopes: ScopeStore = Depends(get_scopes),
    ):
        try:
            scopes.delete_scope(scope_id)
        except KeyError:
            response.status_code = status.HTTP_404_NOT_FOUND

    @router.get("/scopes/{scope_id}/bundle", response_model=PolicyBundle)
    async def get_bundle(
        scope_id: str = Path(..., title="Scope ID to be deleted"),
        scopes: ScopeStore = Depends(get_scopes),
        base_hash: Optional[str] = Query(
            None, description="hash of previous bundle already downloaded, server will return a diff bundle.")
    ):
        scope = scopes.get_scope(scope_id)
        repo = Repo(scope.location)

        bundle_maker = BundleMaker(
            repo,
            {pathlib.Path(".")},
            extensions=opal_server_config.OPA_FILE_EXTENSIONS,
            manifest_filename=opal_server_config.POLICY_REPO_MANIFEST_PATH,
        )

        return make_bundle(bundle_maker, repo, base_hash)

    @router.post("/scopes/periodic-check")
    async def periodic_check(
        scopes: ScopeStore = Depends(get_scopes)
    ):
        for scope_id, scope in scopes.scopes.items():
            if not scope.config.source.polling:
                continue

            puller = create_puller(scopes.base_dir, scope.config)

            if puller.check():
                puller.pull()
                ### PUBSUB

    return router
