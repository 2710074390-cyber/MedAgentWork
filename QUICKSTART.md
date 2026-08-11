# 医学复习资料库 — 快速开始

## 📦 当前状态

✅ 目录结构已构建完成
⏳ 等待复制 HTML 产物文件
⏳ 等待部署到 GitHub Pages

## 🚀 三步上线

### 第一步：复制产物文件

运行部署脚本（自动复制）：

```bash
cd "C:/Users/38063/Desktop/Web-AI/med-site-demos/demo-a-github-pages"
bash deploy.sh
```

或手动复制：

```bash
# 押题卷
cp "C:/Users/38063/Desktop/MedAgentWork/最终产物/内科学押题卷_2026.html" exam/
cp "C:/Users/38063/Desktop/MedAgentWork/最终产物/精神病学押题卷_2026.html" exam/
cp "C:/Users/38063/Desktop/MedAgentWork/最终产物/神经病学押题卷_2026.html" exam/
cp "C:/Users/38063/Desktop/MedAgentWork/最终产物/医患沟通押题卷_2026.html" exam/
cp "C:/Users/38063/Desktop/MedAgentWork/最终产物/batch022/外科学押题卷_108题.html" exam/

# 复习手册
cp "C:/Users/38063/Desktop/MedAgentWork/复习资料/精神病学_主复习资料.html" review/
cp "C:/Users/38063/Desktop/MedAgentWork/复习资料/中医学_主复习资料.html" review/
cp "C:/Users/38063/Desktop/MedAgentWork/复习资料/batch006_外科学一_主复习资料.html" review/
cp "C:/Users/38063/Desktop/MedAgentWork/复习资料/batch008_中医心理学_主复习资料.html" review/
```

### 第二步：本地预览

```bash
cd "C:/Users/38063/Desktop/Web-AI/med-site-demos/demo-a-github-pages"

# 方式 1：使用 npx serve（推荐）
npx serve .

# 方式 2：使用 Python
python -m http.server 8000

# 方式 3：使用 Node.js http-server
npx http-server .
```

访问: http://localhost:3000（或对应端口）

检查：
- [ ] 主页导航正常
- [ ] 押题卷链接可点击
- [ ] 复习手册链接可点击
- [ ] 学科索引页正常
- [ ] 移动端适配良好

### 第三步：推送到 GitHub

```bash
cd "C:/Users/38063/Desktop/Web-AI/med-site-demos/demo-a-github-pages"

# 初始化 Git 仓库
git init
git add .
git commit -m "🎉 初始化医学复习资料库"

# 创建 GitHub 仓库（在浏览器中）
# 访问: https://github.com/new
# 仓库名: med-review-site
# 可见性: Public

# 关联远程仓库
git branch -M main
git remote add origin https://github.com/2710074390-cyber/med-review-site.git
git push -u origin main
```

### 第四步：开启 GitHub Pages

1. 访问: https://github.com/2710074390-cyber/med-review-site/settings/pages
2. **Source** 选择 **Deploy from a branch**
3. **Branch** 选择 `main`，文件夹选 `/ (root)`
4. 点击 **Save**

等待 1-2 分钟后，访问:
**https://2710074390-cyber.github.io/med-review-site/**

## 🔒 隐私保护检查清单

- ✅ 无 API 密钥
- ✅ 无 Token
- ✅ 无密码
- ✅ 无敏感个人信息
- ✅ 所有 HTML 自包含，无外部请求
- ✅ .gitignore 已配置

## 📝 后续更新

每次新增内容后：

```bash
# 1. 复制新文件到对应目录
# 2. 更新 index.html 添加新卡片
# 3. 提交并推送
git add .
git commit -m "✨ 新增：XXX"
git push
```

GitHub Pages 会自动更新（1-2 分钟）。

## 🐛 常见问题

### 页面 404
- 检查文件路径是否正确
- 检查 `index.html` 中的链接是否匹配文件名

### 样式丢失
- 检查 HTML 文件是否完整复制
- 确认文件编码为 UTF-8

### GitHub Pages 未更新
- 等待 2-3 分钟
- 检查 Actions 标签页是否有构建错误
- 清除浏览器缓存

## 📚 参考资源

- [GitHub Pages 文档](https://docs.github.com/zh/pages)
- [自定义域名](https://docs.github.com/zh/pages/configuring-a-custom-domain-for-your-github-pages-site)
- [MedAgentWork 项目](https://github.com/2710074390-cyber/MedAgentWork)

---

**准备就绪后，运行 `bash deploy.sh` 开始部署！**
