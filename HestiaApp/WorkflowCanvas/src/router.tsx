import { createHashRouter, RouterProvider } from 'react-router-dom';
import WorkflowApp from './WorkflowApp';
import ResearchApp from './research/ResearchApp';

const router = createHashRouter([
  { path: '/', element: <WorkflowApp /> },
  { path: '/workflow', element: <WorkflowApp /> },
  { path: '/research', element: <ResearchApp /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
