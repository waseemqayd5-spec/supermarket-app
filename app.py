"""
خوارزمية A* (A Star) للبحث عن أقصر مسار باستخدام المنطق التقديري (Heuristics)
تعتمد على المعادلة: f(n) = g(n) + h(n)
- g(n): التكلفة الفعلية من البداية إلى العقدة n
- h(n): التكلفة التقديرية (المسافة المتوقعة) من العقدة n إلى الهدف
- f(n): الأولوية الكلية (كلما قلت، كان المسار أفضل)
"""

import heapq
import math

class Node:
    """تمثيل عقدة في الرسم البياني"""
    def __init__(self, name, x, y):
        self.name = name      # اسم العقدة (مثل 'A', 'B')
        self.x = x            # الإحداثي x (لحساب المسافة الإقليدية)
        self.y = y            # الإحداثي y
        self.g = float('inf') # التكلفة الفعلية من البداية
        self.h = 0            # التكلفة التقديرية إلى الهدف
        self.f = float('inf') # f = g + h
        self.parent = None    # العقدة الأب (لتتبع المسار)

    def __lt__(self, other):
        return self.f < other.f

class Graph:
    """تمثيل الرسم البياني (الخريطة)"""
    def __init__(self):
        self.nodes = {}       # قاموس {اسم العقدة: كائن Node}
        self.edges = {}       # قاموس {اسم العقدة: {الجار: التكلفة}}

    def add_node(self, name, x, y):
        self.nodes[name] = Node(name, x, y)
        self.edges[name] = {}

    def add_edge(self, from_node, to_node, cost):
        self.edges[from_node][to_node] = cost
        self.edges[to_node][from_node] = cost  # إذا كان الرسم البياني غير موجه

    def heuristic(self, node_name, goal_name):
        """
        دالة التقدير (h(n)): تستخدم المسافة الإقليدية بين النقطة الحالية والهدف.
        هذه هي "الذكاء" في الخوارزمية.
        """
        node = self.nodes[node_name]
        goal = self.nodes[goal_name]
        # المسافة الإقليدية (Euclidean distance)
        return math.sqrt((node.x - goal.x) ** 2 + (node.y - goal.y) ** 2)

    def a_star_search(self, start_name, goal_name):
        """
        تنفيذ خوارزمية A* للبحث عن أقصر مسار من start إلى goal.
        تعيد: (أقصر مسار كقائمة من الأسماء, التكلفة الإجمالية)
        """
        # تهيئة العقدة البداية
        start = self.nodes[start_name]
        start.g = 0
        start.h = self.heuristic(start_name, goal_name)
        start.f = start.g + start.h

        # قائمة الأولويات (priority queue) – تستخدم heap
        open_set = []
        heapq.heappush(open_set, start)

        # مجموعة العقد التي تمت زيارتها بالفعل
        closed_set = set()

        while open_set:
            # نأخذ العقدة ذات أقل f(n)
            current = heapq.heappop(open_set)

            # إذا وصلنا إلى الهدف، نعيد بناء المسار
            if current.name == goal_name:
                path = []
                total_cost = current.g
                while current:
                    path.append(current.name)
                    current = current.parent
                path.reverse()
                return path, total_cost

            closed_set.add(current.name)

            # فحص جميع جيران العقدة الحالية
            for neighbor_name, edge_cost in self.edges[current.name].items():
                if neighbor_name in closed_set:
                    continue

                neighbor = self.nodes[neighbor_name]
                tentative_g = current.g + edge_cost

                # إذا وجدنا مساراً أفضل إلى هذا الجار
                if tentative_g < neighbor.g:
                    neighbor.parent = current
                    neighbor.g = tentative_g
                    neighbor.h = self.heuristic(neighbor_name, goal_name)
                    neighbor.f = neighbor.g + neighbor.h

                    # إذا لم يكن الجار في open_set، نضيفه
                    if neighbor not in open_set:
                        heapq.heappush(open_set, neighbor)

        # إذا انتهت الحلقة دون إيجاد هدف
        return None, float('inf')


# ==================================================
# مثال تطبيقي: إيجاد أقصر مسار بين مدن
# ==================================================

def run_example():
    print("=" * 50)
    print("خوارزمية A* - البحث عن أقصر مسار بين المدن")
    print("=" * 50)

    # إنشاء الرسم البياني
    graph = Graph()

    # إضافة المدن (العقد) مع إحداثيات وهمية (x, y)
    # يمكن اعتبارها مواقع على الخريطة
    cities = {
        'الرياض': (0, 0),
        'جدة': (10, 5),
        'مكة': (9, 4),
        'الدمام': (12, 2),
        'المدينة': (5, 7),
        'الطائف': (7, 3),
        'بريدة': (4, 2),
        'أبها': (15, 8)
    }

    for name, (x, y) in cities.items():
        graph.add_node(name, x, y)

    # إضافة الطرق (الحواف) مع التكاليف (المسافات التقريبية)
    # التكلفة هنا هي المسافة المستقيمة (يمكن حسابها من الإحداثيات، لكن نضعها يدوياً للتبسيط)
    edges = [
        ('الرياض', 'جدة', 850),
        ('الرياض', 'الدمام', 400),
        ('الرياض', 'بريدة', 330),
        ('جدة', 'مكة', 80),
        ('جدة', 'المدينة', 420),
        ('جدة', 'الطائف', 180),
        ('مكة', 'الطائف', 90),
        ('المدينة', 'بريدة', 540),
        ('الدمام', 'أبها', 1200),
        ('الطائف', 'أبها', 700),
        ('بريدة', 'الرياض', 330),
    ]

    for from_node, to_node, cost in edges:
        graph.add_edge(from_node, to_node, cost)

    # طلب إدخال من المستخدم
    print("\nالمدن المتاحة:")
    for name in cities.keys():
        print(f"  - {name}")

    start = input("\nأدخل اسم مدينة البداية: ").strip()
    goal = input("أدخل اسم مدينة الهدف: ").strip()

    if start not in graph.nodes or goal not in graph.nodes:
        print("❌ خطأ: اسم المدينة غير موجود.")
        return

    # تنفيذ البحث
    path, cost = graph.a_star_search(start, goal)

    if path:
        print(f"\n✅ أقصر مسار من {start} إلى {goal}:")
        print("   → ".join(path))
        print(f"📏 التكلفة الإجمالية: {cost} كم")
    else:
        print(f"\n❌ لم يتم العثور على مسار من {start} إلى {goal}")


# ==================================================
# مثال إضافي: متاهة (شبكة ثنائية الأبعاد)
# ==================================================

def run_maze_example():
    print("\n" + "=" * 50)
    print("خوارزمية A* - إيجاد أقصر مسار في متاهة")
    print("=" * 50)

    # متاهة 10x10 (0 = ممر، 1 = جدار)
    maze = [
        [0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 1, 1, 0, 1, 0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
        [1, 1, 1, 1, 0, 1, 1, 0, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
        [0, 1, 1, 1, 1, 1, 1, 0, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 1, 1, 1, 1, 1, 1, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    ]

    start = (0, 0)   # نقطة البداية (صف, عمود)
    goal = (9, 9)    # نقطة الهدف

    # دالة التقدير: المسافة المانهاتن (Manhattan distance)
    def heuristic_maze(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # تنفيذ A* للمتاهة
    path = a_star_maze(maze, start, goal, heuristic_maze)

    if path:
        print(f"✅ تم إيجاد مسار من {start} إلى {goal}")
        print("المسار:", path)
        print(f"عدد الخطوات: {len(path)-1}")
        # طباعة المتاهة مع المسار
        print("\nتمثيل المتاهة (* = المسار, # = جدار, . = ممر):")
        maze_copy = [row[:] for row in maze]
        for r, c in path:
            if (r, c) != start and (r, c) != goal:
                maze_copy[r][c] = '*'
        for r in range(len(maze_copy)):
            row_str = ''
            for c in range(len(maze_copy[0])):
                if (r, c) == start:
                    row_str += 'S'
                elif (r, c) == goal:
                    row_str += 'G'
                elif maze_copy[r][c] == 1:
                    row_str += '#'
                elif maze_copy[r][c] == '*':
                    row_str += '*'
                else:
                    row_str += '.'
            print(row_str)
    else:
        print("❌ لا يوجد مسار من البداية إلى الهدف")

def a_star_maze(maze, start, goal, heuristic):
    """تنفيذ A* للمتاهة"""
    rows, cols = len(maze), len(maze[0])
    open_set = []
    heapq.heappush(open_set, (0, start))  # (f, position)

    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    came_from = {}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            # إعادة بناء المسار
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path

        # الاتجاهات: أعلى، أسفل، يسار، يمين
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            neighbor = (current[0] + dr, current[1] + dc)
            # التحقق من صحة الخلية وعدم وجود جدار
            if 0 <= neighbor[0] < rows and 0 <= neighbor[1] < cols:
                if maze[neighbor[0]][neighbor[1]] == 1:
                    continue

                tentative_g = g_score[current] + 1  # تكلفة الخطوة = 1

                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

    return None  # لا يوجد مسار


# ==================================================
# تشغيل الأمثلة
# ==================================================
if __name__ == "__main__":
    # المثال الأول: المدن
    run_example()

    # المثال الثاني: المتاهة
    run_maze_example()
