import { memo } from 'react';

function LaneNode({ data }) {
  const { lane } = data;
  return (
    <div className="lane">
      <div className="lane-head">
        <span className="lane-id">{lane.id}</span>
        <div>
          <div className="lane-title">{lane.title}</div>
          <div className="lane-sub">{lane.sub}</div>
        </div>
      </div>
    </div>
  );
}
export default memo(LaneNode);
