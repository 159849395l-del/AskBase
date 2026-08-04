/** 404 页面 */

import React from "react";
import { Button, Result } from "antd";
import { useNavigate } from "react-router-dom";

const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Result
        status="404"
        title="404"
        subTitle="页面不存在"
        extra={
          <Button type="primary" onClick={() => navigate("/chat")}>
            返回聊天
          </Button>
        }
      />
    </div>
  );
};

export default NotFoundPage;
