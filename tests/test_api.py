"""API 测试"""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
import asyncio
import tempfile
import os

from sagents.main import app
from sagents.api.tasks import init_db, close_db, _tasks
from sagents.api.health import _health_monitor


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """创建异步测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def setup_tasks_db():
    """设置任务数据库"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_tasks.db")
        await init_db(db_path)
        yield
        await close_db()


class TestHealthAPI:
    """健康检查 API 测试"""
    
    def test_health_endpoint(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    def test_liveness_probe(self, client):
        """测试存活探针"""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"
    
    def test_readiness_probe(self, client):
        """测试就绪探针"""
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert "status" in response.json()


class TestTasksAPI:
    """任务管理 API 测试"""
    
    @pytest.mark.asyncio
    async def test_create_task(self, async_client, setup_tasks_db):
        """测试创建任务"""
        task_data = {
            "id": "api-test-1",
            "title": "API Test Task",
            "description": "Testing task creation via API",
            "status": "pending",
            "priority": 1,
        }
        
        response = await async_client.post("/tasks", json=task_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["task_id"] == "api-test-1"
        assert data["status"] == "created"
    
    @pytest.mark.asyncio
    async def test_get_task(self, async_client, setup_tasks_db):
        """测试获取任务"""
        # 先创建任务
        task_data = {
            "id": "api-test-get",
            "title": "Get Test Task",
            "description": "Testing task retrieval",
            "status": "pending",
        }
        await async_client.post("/tasks", json=task_data)
        
        # 获取任务
        response = await async_client.get("/tasks/api-test-get")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "api-test-get"
        assert data["title"] == "Get Test Task"
    
    @pytest.mark.asyncio
    async def test_get_task_not_found(self, async_client, setup_tasks_db):
        """测试获取不存在的任务"""
        response = await async_client.get("/tasks/non-existent")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, async_client, setup_tasks_db):
        """测试列出任务"""
        # 创建多个任务
        for i in range(3):
            task_data = {
                "id": f"api-test-list-{i}",
                "title": f"List Test Task {i}",
                "description": f"Task {i}",
                "status": "pending",
            }
            await async_client.post("/tasks", json=task_data)
        
        # 列出所有任务
        response = await async_client.get("/tasks")
        assert response.status_code == 200
        
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert data["total"] >= 3
    
    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self, async_client, setup_tasks_db):
        """测试按状态过滤任务"""
        # 创建不同状态的任务
        await async_client.post("/tasks", json={
            "id": "task-pending",
            "title": "Pending Task",
            "status": "pending",
        })
        await async_client.post("/tasks", json={
            "id": "task-completed",
            "title": "Completed Task",
            "status": "completed",
        })
        
        # 按 pending 状态过滤
        response = await async_client.get("/tasks?status=pending")
        assert response.status_code == 200
        
        data = response.json()
        for task in data["tasks"]:
            assert task["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_update_task(self, async_client, setup_tasks_db):
        """测试更新任务"""
        # 创建任务
        await async_client.post("/tasks", json={
            "id": "api-test-update",
            "title": "Update Test Task",
            "status": "pending",
        })
        
        # 更新任务
        response = await async_client.patch(
            "/tasks/api-test-update",
            json={"status": "in_progress", "priority": 5},
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "updated"
        
        # 验证更新
        get_response = await async_client.get("/tasks/api-test-update")
        updated_task = get_response.json()
        assert updated_task["status"] == "in_progress"
    
    @pytest.mark.asyncio
    async def test_delete_task(self, async_client, setup_tasks_db):
        """测试删除任务"""
        # 创建任务
        await async_client.post("/tasks", json={
            "id": "api-test-delete",
            "title": "Delete Test Task",
            "status": "pending",
        })
        
        # 删除任务
        response = await async_client.delete("/tasks/api-test-delete")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "deleted"
        
        # 验证删除
        get_response = await async_client.get("/tasks/api-test-delete")
        assert get_response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_task_history(self, async_client, setup_tasks_db):
        """测试任务历史"""
        # 创建任务
        await async_client.post("/tasks", json={
            "id": "api-test-history",
            "title": "History Test Task",
            "status": "pending",
        })
        
        # 更新任务
        await async_client.patch(
            "/tasks/api-test-history",
            json={"status": "in_progress"},
        )
        
        # 获取历史
        response = await async_client.get("/tasks/api-test-history/history")
        assert response.status_code == 200
        
        data = response.json()
        assert "history" in data
        assert len(data["history"]) >= 2  # 创建 + 更新


class TestStatusAPI:
    """状态 API 测试"""
    
    def test_status_endpoint(self, client):
        """测试状态端点"""
        response = client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "agents" in data
        assert "version" in data


class TestDocsAPI:
    """文档 API 测试"""
    
    def test_docs_endpoint(self, client):
        """测试文档端点"""
        response = client.get("/docs")
        assert response.status_code == 200
